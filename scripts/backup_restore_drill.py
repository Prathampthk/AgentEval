"""Controlled pg_dump/pg_restore drill; temporary databases and fake work only."""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from agenteval.database import Database
from agenteval.jobs import JobQueue
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider
from agenteval.service import evaluate


def docker(container, *command, **kwargs):
    environment = os.environ.copy()
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        environment.pop(key, None)
    return subprocess.run(
        ["docker", "--host=unix:///var/run/docker.sock", "exec", "-i", container, *command],
        env=environment,
        check=True,
        **kwargs,
    )


async def main(args):
    raw = os.environ.get("AGENTEVAL_TEST_DATABASE_URL")
    if not raw:
        raise RuntimeError("Dedicated local PostgreSQL test URL required")
    base = make_url(raw)
    if (
        base.drivername != "postgresql+asyncpg"
        or base.host not in ("127.0.0.1", "localhost")
        or not base.database.endswith("_test")
    ):
        raise RuntimeError("This drill supports only the local dedicated test deployment")
    suffix = uuid4().hex[:10]
    names = [f"agenteval_drill_{role}_{suffix}_test" for role in ("source", "restore")]
    created, clients = [], []
    folder = Path(".local/backups")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = folder / f"{suffix}.dump"
    outcomes = []
    try:
        for name in names:
            docker(args.container, "createdb", "-U", "postgres", name, capture_output=True)
            created.append(name)
        urls = [base.set(database=name).render_as_string(hide_password=False) for name in names]
        environment = {
            **os.environ,
            "AGENTEVAL_DATABASE_URL": urls[0],
            "AGENTEVAL_MIGRATION_DATABASE_URL": urls[0],
        }
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            check=True,
            capture_output=True,
        )
        source = Database(urls[0])
        clients.append(source)
        provider = FakeProvider()
        queue = JobQueue(source)
        dataset, _ = await source.create_dataset(
            DatasetCreate(
                name="restore-drill",
                version="1",
                cases=[
                    dict(
                        external_id="one",
                        question="Capital of France?",
                        expected_answer="Paris",
                        context="Paris",
                    )
                ],
            )
        )
        data = RunCreate(dataset_id=dataset.id)
        completed = await queue.submit(data, provider, "completed-drill")
        claim = await queue.claim("backup-drill", provider)
        await queue.complete(claim, await evaluate(claim.request, provider))
        pending = await queue.submit(data, provider, "pending-drill")
        with open(backup, "xb", opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
            docker(
                args.container,
                "pg_dump",
                "-U",
                "postgres",
                "-Fc",
                names[0],
                stdout=file,
                stderr=subprocess.PIPE,
            )
        with backup.open("rb") as file:
            docker(
                args.container,
                "pg_restore",
                "-U",
                "postgres",
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
                "-d",
                names[1],
                stdin=file,
                capture_output=True,
            )
        target = Database(urls[1])
        clients.append(target)
        await target.check_ready()
        restored = JobQueue(target)
        run = await target.get_run(completed)
        assert run.status == "COMPLETED" and len(run.results) == 1
        outcomes.append("completed result and run identity restored")
        assert (await restored.list_jobs(pending))[0].status == "PENDING"
        outcomes.append("pending durable work restored")
        assert await restored.submit(data, provider, "completed-drill") == completed
        outcomes.append("submission idempotency survived restoration")
        replacement = await restored.claim("restored-worker", provider)
        assert replacement.run_id == pending
        await restored.complete(replacement, await evaluate(replacement.request, provider))
        assert len((await target.get_run(pending)).results) == 1
        outcomes.append("restored pending work executed with one accepted result")
    finally:
        for client in clients:
            await client.close()
        for name in reversed(created):
            docker(args.container, "dropdb", "-U", "postgres", "--force", name, capture_output=True)
    report = dict(
        status="PASS",
        verified_at_utc=datetime.now(UTC).isoformat(),
        checks=outcomes,
        backup_bytes=backup.stat().st_size,
        temporary_databases_removed=True,
        simulated=True,
        live_provider_calls=0,
        limitations=[
            "Controlled local idle-source snapshot; no storage corruption/host loss/HA/PITR proof.",
            "No production backup scheduling, encryption, retention, offsite storage or RPO/RTO SLA verified.",
            "Local dump contains only generated drill data and remains in ignored .local/backups.",
        ],
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="agenteval-postgres")
    parser.add_argument("--output", default="reports/backup-restore-drill.json")
    arguments = parser.parse_args()
    if not re.fullmatch("[A-Za-z0-9_.-]+", arguments.container):
        parser.error("Invalid local container name")
    asyncio.run(main(arguments))
