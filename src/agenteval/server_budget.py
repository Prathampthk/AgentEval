"""Persistent, single-host SDK admission ledger shared by private API and workers."""

import argparse
import asyncio
import base64
import json
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from agenteval.providers import ProviderError


class ServerBudget:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("Server budget requires an absolute persistent path")

    @contextmanager
    def connection(self):
        connection = None
        try:
            if self.path.stat().st_mode & 0o077:
                raise ValueError("Budget ledger must exclude group/other access")
            connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except (sqlite3.Error, OSError, ValueError):
            raise ProviderError("provider_budget_unavailable") from None
        finally:
            if connection:
                connection.close()

    @staticmethod
    def _policy(connection):
        row = connection.execute("SELECT ceiling,rpm,concurrency FROM policy WHERE id=1").fetchone()
        if (
            row is None
            or not all(type(value) is int for value in row)
            or not (1 <= row[0] <= 100000 and 1 <= row[1] <= 1000 and 1 <= row[2] <= 4)
        ):
            raise ValueError("Invalid server budget policy")
        return row

    def validate(self):
        with self.connection() as connection:
            self._policy(connection)

    def reserve(self, operation):
        if operation not in {"generate", "judge", "embed"}:
            raise ValueError("Unknown provider operation")
        with self.connection() as connection:
            now = time.time()
            ceiling, rpm, concurrency = self._policy(connection)
            total, active = connection.execute(
                "SELECT count(*),count(*) FILTER (WHERE finished IS NULL) FROM attempts"
            ).fetchone()
            if total >= ceiling:
                raise ProviderError("provider_budget_exhausted")
            if active >= concurrency:
                raise ProviderError("provider_capacity", retryable=True, retry_after_seconds=1)
            count, oldest = connection.execute(
                "SELECT count(*),min(started) FROM attempts WHERE started>?", (now - 60,)
            ).fetchone()
            if count >= rpm:
                raise ProviderError(
                    "provider_rate_limited",
                    retryable=True,
                    retry_after_seconds=max(1, math.ceil(oldest + 60 - now)),
                )
            identifier = uuid4().hex
            connection.execute(
                "INSERT INTO attempts(id,operation,started) VALUES(?,?,?)",
                (identifier, operation, now),
            )
        return identifier

    def finish(self, identifier, response, succeeded):
        usage = getattr(response, "usage", None)
        with self.connection() as connection:
            connection.execute(
                "UPDATE attempts SET finished=?,succeeded=?,input_tokens=?,output_tokens=? WHERE id=?",
                (
                    time.time(),
                    int(succeeded),
                    getattr(usage, "input_tokens", None),
                    getattr(usage, "output_tokens", None),
                    identifier,
                ),
            )

    def status(self):
        with self.connection() as connection:
            policy = self._policy(connection)
            total, active = connection.execute(
                "SELECT count(*),count(*) FILTER (WHERE finished IS NULL) FROM attempts"
            ).fetchone()
        return {
            "attempt_ceiling": policy[0],
            "requests_per_minute": policy[1],
            "concurrency": policy[2],
            "attempts_reserved": total,
            "active_or_uncertain": active,
            "attempts_remaining": max(0, policy[0] - total),
        }

    def active(self):
        with self.connection() as connection:
            return [
                dict(id=row[0], operation=row[1], started=row[2])
                for row in connection.execute(
                    "SELECT id,operation,started FROM attempts WHERE finished IS NULL"
                )
            ]

    def reconcile(self, identifiers):
        if not identifiers or len(set(identifiers)) != len(identifiers):
            raise ValueError("Choose explicit distinct uncertain attempt IDs")
        with self.connection() as connection:
            for identifier in identifiers:
                if connection.execute(
                    "SELECT finished FROM attempts WHERE id=?", (identifier,)
                ).fetchone() != (None,):
                    raise ValueError("Attempt is missing or already closed")
            for identifier in identifiers:
                connection.execute(
                    "UPDATE attempts SET finished=?,succeeded=0 WHERE id=?",
                    (time.time(), identifier),
                )

    def snapshot(self):
        with self.connection() as connection:
            return connection.serialize()


def configure(path, ceiling, rpm, concurrency):
    if (
        type(ceiling) is not int
        or type(rpm) is not int
        or type(concurrency) is not int
        or not 1 <= ceiling <= 100000
        or not 1 <= rpm <= 1000
        or not 1 <= concurrency <= 4
    ):
        raise ValueError("Invalid bounded policy")
    budget = ServerBudget(path)
    budget.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with open(budget.path, "x", opener=lambda p, f: os.open(p, f, 0o600)):
            pass
    except FileExistsError:
        pass
    with budget.connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1),ceiling INTEGER NOT NULL,rpm INTEGER NOT NULL,concurrency INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,operation TEXT NOT NULL,started REAL NOT NULL,finished REAL,succeeded INTEGER,input_tokens INTEGER,output_tokens INTEGER)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS attempts_started ON attempts(started)")
        total, active = connection.execute(
            "SELECT count(*),count(*) FILTER (WHERE finished IS NULL) FROM attempts"
        ).fetchone()
        if active or ceiling < total:
            raise ValueError(
                "Reconcile uncertain operations first; ceilings cannot erase spent attempts"
            )
        connection.execute(
            "INSERT INTO policy VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET ceiling=excluded.ceiling,rpm=excluded.rpm,concurrency=excluded.concurrency",
            (ceiling, rpm, concurrency),
        )
    return budget


class BudgetProvider:
    def __init__(self, provider, budget):
        self.provider, self.budget = provider, budget

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def with_judge_prompt(self, version):
        return BudgetProvider(self.provider.with_judge_prompt(version), self.budget)

    async def call(self, operation, data):
        identifier = await asyncio.to_thread(self.budget.reserve, operation)
        response, succeeded, uncertain = None, False, False
        try:
            response = await getattr(self.provider, operation)(data)
            succeeded = True
            return response
        except BaseException as exc:
            uncertain = not isinstance(exc, ProviderError) or exc.category in {
                "timeout",
                "network",
                "unavailable",
                "provider_error",
            }
            raise
        finally:
            if not uncertain:
                await asyncio.shield(
                    asyncio.to_thread(self.budget.finish, identifier, response, succeeded)
                )

    async def generate(self, data):
        return await self.call("generate", data)

    async def judge(self, data):
        return await self.call("judge", data)

    async def embed(self, data):
        return await self.call("embed", data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=os.getenv("AGENTEVAL_SERVER_BUDGET_DB"))
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure")
    setup.add_argument("--max-attempts", required=True, type=int)
    setup.add_argument("--requests-per-minute", required=True, type=int)
    setup.add_argument("--concurrency", type=int, default=1)
    commands.add_parser("status")
    commands.add_parser("inspect-active")
    commands.add_parser("snapshot")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--attempt", action="append", required=True)
    reconcile.add_argument("--confirm-workers-stopped", action="store_true", required=True)
    reconcile.add_argument("--confirm-provider-usage-reviewed", action="store_true", required=True)
    args = parser.parse_args()
    try:
        if args.path is None:
            raise ValueError("A persistent budget path is required")
        if args.command == "snapshot" and not args.path.exists():
            print(json.dumps({"configured": False}))
            return
        budget = (
            configure(args.path, args.max_attempts, args.requests_per_minute, args.concurrency)
            if args.command == "configure"
            else ServerBudget(args.path)
        )
        if args.command == "inspect-active":
            print(json.dumps(budget.active()))
            return
        if args.command == "reconcile":
            budget.reconcile(args.attempt)
            try:
                print(json.dumps(budget.status()))
            except ProviderError:
                print(
                    json.dumps(
                        {
                            "reconciled_attempts": len(args.attempt),
                            "attempts_refunded": 0,
                            "policy_status": "unavailable",
                        }
                    )
                )
            return
        budget.validate()
        if args.command == "snapshot":
            print(
                json.dumps(
                    {
                        "configured": True,
                        "sqlite_base64": base64.b64encode(budget.snapshot()).decode(),
                    }
                )
            )
        else:
            print(json.dumps(budget.status()))
    except (ValueError, ProviderError):
        parser.error("Budget unavailable or policy rejected; no provider requests were made")


if __name__ == "__main__":
    main()
