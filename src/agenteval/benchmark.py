"""Reproducible PostgreSQL worker benchmark. Always simulated; never calls Gemini."""

import argparse
import asyncio
import json
import math
import os
import platform
import random
import resource
import statistics
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from agenteval.database import Database
from agenteval.jobs import JobQueue
from agenteval.models import Job, Result, Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider, ProviderError
from agenteval.worker import WorkerMetrics, serve


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return None

    def quantile(p):
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)]

    return {
        "count": len(ordered),
        "mean": statistics.mean(ordered),
        "p50": quantile(0.5),
        "p95": quantile(0.95),
        "p99": quantile(0.99),
    }


class SimulatedProvider(FakeProvider):
    def __init__(self, model, latency, failure_every):
        self.model = model
        self.latency = latency
        self.failure_every = failure_every
        self.calls = {}
        self.latencies = []

    async def generate(self, data):
        start = perf_counter()
        try:
            await asyncio.sleep(self.latency)
            self.calls[data.question] = self.calls.get(data.question, 0) + 1
            index = int(data.question.split()[-1])
            if (
                self.failure_every
                and index % self.failure_every == 0
                and self.calls[data.question] == 1
            ):
                raise ProviderError("rate_limit", True)
            return await super().generate(data)
        finally:
            self.latencies.append((perf_counter() - start) * 1000)

    async def judge(self, data):
        start = perf_counter()
        try:
            await asyncio.sleep(self.latency)
            return await super().judge(data)
        finally:
            self.latencies.append((perf_counter() - start) * 1000)


class MeasuredQueue(JobQueue):
    def __init__(self, database, stop, total):
        super().__init__(database)
        self.stop, self.total = stop, total
        self.started = 0
        self.first_claim = {}
        self.accepted = {}

    async def claim(self, *args, **kwargs):
        claim = await super().claim(*args, **kwargs)
        if claim:
            self.first_claim.setdefault(str(claim.id), (perf_counter() - self.started) * 1000)
        return claim

    async def complete(self, claim, result):
        await super().complete(claim, result)
        self.accepted[str(claim.id)] = (perf_counter() - self.started) * 1000
        if len(self.accepted) == self.total:
            self.stop.set()


async def variant(database, args, rep, concurrency):
    identifier = uuid4().hex[:12]
    provider = SimulatedProvider(f"simulation-{identifier}", args.latency, args.failure_every)
    stop = asyncio.Event()
    queue = MeasuredQueue(database, stop, args.jobs)
    for block in range(0, args.jobs, 20):
        data = DatasetCreate(
            name=f"benchmark-{identifier}-{block}",
            version="1",
            cases=[
                dict(
                    external_id=str(index),
                    question=f"case {index}",
                    expected_answer="Paris",
                    context="Paris",
                )
                for index in range(block, min(block + 20, args.jobs))
            ],
        )
        dataset, _ = await database.create_dataset(data)
        await queue.submit(RunCreate(dataset_id=dataset.id), provider, f"{identifier}-{block}")
    random.seed(args.seed + rep)
    metrics = WorkerMetrics()
    cpu_before = resource.getrusage(resource.RUSAGE_SELF)
    queue.started = perf_counter()
    async with asyncio.timeout(180):
        await serve(
            stop,
            queue,
            provider,
            "benchmark-" + identifier,
            concurrency=concurrency,
            poll_seconds=0.01,
            metrics=metrics,
        )
    duration = perf_counter() - queue.started
    cpu_after = resource.getrusage(resource.RUSAGE_SELF)
    async with database.sessions() as session:
        jobs = (
            await session.execute(
                select(Job.status, Job.attempts)
                .join(Run, Run.id == Job.run_id)
                .where(Run.model == provider.model)
            )
        ).all()
        results = (
            await session.scalars(
                select(Result).join(Run, Run.id == Result.run_id).where(Run.model == provider.model)
            )
        ).all()
    assert len(results) == args.jobs == len(queue.accepted)
    assert all(status == "COMPLETED" for status, _ in jobs)
    assert metrics.max_active_evaluations <= concurrency and metrics.active_evaluations == 0
    raw = [
        {
            "job_id": str(row.job_id),
            "queue_wait_ms": queue.first_claim[str(row.job_id)],
            "completion_ms": queue.accepted[str(row.job_id)],
            "execution_ms": row.generation_latency_ms + row.judge_latency_ms,
        }
        for row in results
    ]
    return {
        "repetition": rep,
        "concurrency": concurrency,
        "simulated": True,
        "cache_enabled": False,
        "jobs_completed": len(results),
        "duration_seconds": duration,
        "throughput_jobs_per_second": args.jobs / duration,
        "max_active_evaluations": metrics.max_active_evaluations,
        "retry_count": sum(attempts - 1 for _, attempts in jobs),
        "error_rate": 0,
        "token_usage": None,
        "token_usage_note": "No billable token metadata from simulated provider",
        "cache_hit_rate": None,
        "provider_request_latency_ms": distribution(provider.latencies),
        "queue_wait_ms": distribution([r["queue_wait_ms"] for r in raw]),
        "execution_ms": distribution([r["execution_ms"] for r in raw]),
        "completion_ms": distribution([r["completion_ms"] for r in raw]),
        "cpu_seconds": cpu_after.ru_utime
        + cpu_after.ru_stime
        - cpu_before.ru_utime
        - cpu_before.ru_stime,
        "process_peak_rss_kib": cpu_after.ru_maxrss,
        "raw_jobs": raw,
    }


async def experiment(args, url):
    database = Database(url)
    try:
        await database.check_ready()
        async with database.sessions() as session:
            pg = await session.scalar(text("SELECT version()"))
            active = await session.scalar(
                text("SELECT count(*) FROM evaluation_jobs WHERE status IN ('PENDING','RUNNING')")
            )
        if active:
            raise RuntimeError(
                "Unfinished benchmark jobs already exist; inspect or cancel them before a new experiment"
            )
        report = {
            "kind": "simulated-postgresql-worker-benchmark",
            "jobs_per_variant": args.jobs,
            "repetitions": args.repetitions,
            "latency_seconds_per_operation": args.latency,
            "failure_every": args.failure_every,
            "seed": args.seed,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "logical_cpus_reported": os.cpu_count(),
            "postgresql": pg,
            "sqlalchemy": version("sqlalchemy"),
            "cache_enabled": False,
            "results": [],
        }
        for rep in range(1, args.repetitions + 1):
            for concurrency in (1, 16):
                result = await variant(database, args, rep, concurrency)
                report["results"].append(result)
                print(
                    json.dumps(
                        {
                            k: result[k]
                            for k in (
                                "repetition",
                                "concurrency",
                                "jobs_completed",
                                "duration_seconds",
                                "retry_count",
                            )
                        }
                    ),
                    flush=True,
                )
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
        sequential = [r["duration_seconds"] for r in report["results"] if r["concurrency"] == 1]
        concurrent = [r["duration_seconds"] for r in report["results"] if r["concurrency"] == 16]
        report["summary"] = {
            "mean_sequential_seconds": statistics.mean(sequential),
            "mean_concurrent_seconds": statistics.mean(concurrent),
            "speedup_ratio_of_mean_times": statistics.mean(sequential)
            / statistics.mean(concurrent),
            "sequential_stdev_seconds": statistics.stdev(sequential)
            if len(sequential) > 1
            else None,
            "concurrent_stdev_seconds": statistics.stdev(concurrent)
            if len(concurrent) > 1
            else None,
        }
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["summary"]), flush=True)
    finally:
        await database.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--latency", type=float, default=0.005)
    parser.add_argument("--failure-every", type=int, default=97)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="reports/benchmark.json")
    args = parser.parse_args()
    if (
        not 1 <= args.jobs <= 1000
        or not 1 <= args.repetitions <= 5
        or not math.isfinite(args.latency)
        or not 0 < args.latency <= 1
        or args.failure_every < 0
    ):
        parser.error("Invalid bounded benchmark parameters")
    url = os.environ.get("AGENTEVAL_BENCHMARK_DATABASE_URL")
    if not url or not make_url(url).database.endswith("_benchmark"):
        parser.error(
            "A dedicated AGENTEVAL_BENCHMARK_DATABASE_URL ending in _benchmark is required"
        )
    env = {**os.environ, "AGENTEVAL_DATABASE_URL": url, "AGENTEVAL_MIGRATION_DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        check=True,
        capture_output=True,
    )
    asyncio.run(experiment(args, url))


if __name__ == "__main__":
    main()
