"""Isolated simulated worker for reproducible process benchmarks/failure injection."""

import argparse
import asyncio
import json
import logging
import os
import random
import resource
import signal
from pathlib import Path
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.engine import make_url

from agenteval.database import Database
from agenteval.diagnostics import WorkerTrace, instrument_sql
from agenteval.jobs import JobQueue
from agenteval.providers import FakeProvider, ProviderError
from agenteval.worker import serve


def atomic(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


class ProcessProvider(FakeProvider):
    def __init__(self, config, trace):
        self.model = config["model"]
        self.config, self.trace = config, trace
        self.current = None
        self.started = None
        self.ended = None

    async def generate(self, data):
        start = perf_counter()
        self.started = start
        try:
            await asyncio.sleep(self.config["latency"])
            index = int(data.question.split()[-1])
            if (
                self.config["failure_every"]
                and index % self.config["failure_every"] == 0
                and self.current.attempt == 1
            ):
                raise ProviderError("rate_limit", True)
            if self.config["scenario"] == "recovery":
                with (Path(self.config["control"]) / f"effects-{os.getpid()}.jsonl").open(
                    "a"
                ) as file:
                    file.write(
                        json.dumps(
                            {"job_id": str(self.current.id), "attempt": self.current.attempt}
                        )
                        + "\n"
                    )
                    file.flush()
                    os.fsync(file.fileno())
            return await super().generate(data)
        except BaseException:
            self.trace.write(
                json.dumps({"kind": "failed-evaluation", "start": start, "end": perf_counter()})
                + "\n"
            )
            raise
        finally:
            self.trace.write(
                json.dumps({"kind": "provider-operation", "start": start, "end": perf_counter()})
                + "\n"
            )

    async def judge(self, data):
        start = perf_counter()
        try:
            await asyncio.sleep(self.config["latency"])
            return await super().judge(data)
        finally:
            self.ended = perf_counter()
            self.trace.write(
                json.dumps({"kind": "evaluation", "start": self.started, "end": self.ended}) + "\n"
            )
            self.trace.write(
                json.dumps({"kind": "provider-operation", "start": start, "end": self.ended}) + "\n"
            )


class ProcessQueue(JobQueue):
    def __init__(self, database, provider, config, trace):
        super().__init__(database)
        self.provider, self.config, self.trace = provider, config, trace
        self.claimed_at = None

    async def claim(self, *args, **kwargs):
        claim = await super().claim(*args, **kwargs)
        if claim:
            self.provider.current = claim
            self.claimed_at = perf_counter()
            random.seed(self.config["seed"] + int(claim.request.test_case_id) * 31 + claim.attempt)
        return claim

    async def complete(self, claim, result):
        if (
            self.config["scenario"] == "recovery"
            and claim.request.test_case_id == "0"
            and claim.attempt == 1
        ):
            atomic(
                Path(self.config["control"]) / "crash.json",
                {
                    "job_id": str(claim.id),
                    "pid": os.getpid(),
                    "time": perf_counter(),
                    "index": self.config["index"],
                },
            )
            os._exit(86)
        await super().complete(claim, result)
        self.trace.write(
            json.dumps(
                {
                    "kind": "accepted",
                    "job_id": str(claim.id),
                    "attempt": claim.attempt,
                    "claimed_at": self.claimed_at,
                    "completed_at": perf_counter(),
                    "evaluation_start": self.provider.started,
                    "evaluation_end": self.provider.ended,
                    "execution_ms": result.generation_latency_ms + result.judge_latency_ms,
                }
            )
            + "\n"
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True)
    parser.add_argument("--index", required=True, type=int)
    parser.add_argument("--generation", default=0, type=int)
    args = parser.parse_args()
    control = Path(args.control)
    config = json.loads((control / "configuration.json").read_text())
    config.update(control=str(control), index=args.index)
    url = os.environ["AGENTEVAL_BENCHMARK_DATABASE_URL"]
    if not make_url(url).database.endswith("_benchmark"):
        raise RuntimeError("A dedicated benchmark database is required")
    database = Database(url, pool_size=2)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    stem = f"{args.index}-{args.generation}"
    try:
        await database.check_ready()
        with (control / f"trace-{stem}.jsonl").open("a", buffering=1) as trace:
            if config.get("diagnostics"):
                logger = logging.getLogger("agenteval.worker")
                logger.setLevel(logging.INFO)
                logger.propagate = False
                logger.addHandler(WorkerTrace(trace))
                instrument_sql(database, trace)
            provider = ProcessProvider(config, trace)
            queue = ProcessQueue(database, provider, config, trace)
            atomic(control / f"ready-{stem}.json", {"pid": os.getpid()})
            async with asyncio.timeout(45):
                while not (control / "start.json").exists():
                    await asyncio.sleep(0.01)

            async def watch():
                while not stop.is_set():
                    if (control / "stop").exists():
                        stop.set()
                    await asyncio.sleep(0.02)

            watch_task = asyncio.create_task(watch())
            try:
                metrics = await serve(
                    stop,
                    queue,
                    provider,
                    f"benchmark-{os.getpid()}",
                    concurrency=1,
                    poll_seconds=0.1,
                    lease_seconds=config["lease_seconds"],
                    heartbeat_seconds=config["heartbeat_seconds"],
                    shutdown_seconds=10,
                )
                async with database.sessions() as session:
                    await session.execute(text("SELECT pg_stat_force_next_flush()"))
                usage = resource.getrusage(resource.RUSAGE_SELF)
                atomic(
                    control / f"exit-{stem}.json",
                    {
                        "pid": os.getpid(),
                        "max_active": metrics.max_active_evaluations,
                        "cpu_seconds": usage.ru_utime + usage.ru_stime,
                        "rss_kib": usage.ru_maxrss,
                    },
                )
            finally:
                watch_task.cancel()
                await asyncio.gather(watch_task, return_exceptions=True)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
