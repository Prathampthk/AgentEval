"""Actual OS-process worker sweep, real PostgreSQL metrics, and crash recovery."""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from agenteval.benchmark import distribution
from agenteval.database import Database
from agenteval.diagnostics import lock_snapshot, wal_snapshot
from agenteval.jobs import JobQueue
from agenteval.models import Job, Result, Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider


async def wait_file(path, timeout=45):
    async with asyncio.timeout(timeout):
        while not path.exists():
            await asyncio.sleep(0.02)
    return json.loads(path.read_text())


def overlap(intervals):
    events = []
    for start, end in intervals:
        events.extend([(start, 1), (end, -1)])
    active = peak = 0
    for _, change in sorted(events):
        active += change
        peak = max(peak, active)
    return peak


async def pg_stats(database):
    async with database.sessions() as session:
        await session.execute(text("SELECT pg_stat_clear_snapshot()"))
        row = (
            (
                await session.execute(
                    text(
                        "SELECT xact_commit,xact_rollback,blks_read,blks_hit,tup_inserted,tup_updated,temp_bytes,deadlocks,blk_read_time,blk_write_time FROM pg_stat_database WHERE datname=current_database()"
                    )
                )
            )
            .mappings()
            .one()
        )
        activity = (
            (
                await session.execute(
                    text(
                        "SELECT count(*) AS connections,count(*) FILTER (WHERE state='active') AS active,count(*) FILTER (WHERE wait_event_type='Lock') AS lock_waiters FROM pg_stat_activity WHERE datname=current_database()"
                    )
                )
            )
            .mappings()
            .one()
        )
        return dict(row), dict(activity)


async def docker_sample(name):
    if not name:
        return None
    env = os.environ.copy()
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(key, None)

    def read():
        result = subprocess.run(
            [
                "docker",
                "--host=unix:///var/run/docker.sock",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                name,
            ],
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        raw = json.loads(result.stdout)
        return {key: raw.get(key) for key in ("CPUPerc", "MemUsage", "BlockIO", "PIDs")}

    try:
        return await asyncio.to_thread(read)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"unavailable": True}


async def variant(database, args, workers, rep, scenario):
    identity = uuid4().hex[:12]
    control = Path(args.output).resolve().parent / ".platform-control" / identity
    control.mkdir(parents=True)
    total = args.jobs if scenario == "throughput" else max(2, workers)
    model = "process-simulation-" + identity
    config = dict(
        model=model,
        diagnostics=getattr(args, "diagnostics", False),
        seed=args.seed,
        latency=args.latency,
        failure_every=args.failure_every if scenario == "throughput" else 0,
        scenario=scenario,
        lease_seconds=60 if scenario == "throughput" else 2,
        heartbeat_seconds=15 if scenario == "throughput" else 0.5,
    )
    (control / "configuration.json").write_text(json.dumps(config))
    provider = FakeProvider()
    provider.model = model
    queue = JobQueue(database)
    run_ids = []
    logical_cases = []
    processes = []
    logs = []

    async def launch(index, generation=0):
        log = (control / f"process-{index}-{generation}.log").open("wb")
        logs.append(log)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "agenteval.platform_actor",
            "--control",
            str(control),
            "--index",
            str(index),
            "--generation",
            str(generation),
            stdout=log,
            stderr=log,
            env=os.environ.copy(),
        )
        processes.append((process, index, generation))
        return process

    db_samples = []
    docker_samples = []
    lock_samples = []
    wal_samples = []
    monitor_stop = asyncio.Event()

    async def monitor():
        tick = 0
        while not monitor_stop.is_set():
            _, sample = await pg_stats(database)
            db_samples.append(sample)
            if config["diagnostics"]:
                lock_samples.append(
                    dict(time=perf_counter(), activity=await lock_snapshot(database))
                )
                wal_samples.append(await wal_snapshot(database))
            if args.postgres_container and tick % 5 == 0:
                docker_samples.append(await docker_sample(args.postgres_container))
            tick += 1
            await asyncio.sleep(0.2)

    monitor_task = None
    succeeded = False
    try:
        for block in range(0, total, 20):
            rows = [
                dict(
                    external_id=str(i),
                    question=f"case {i}",
                    expected_answer="Paris",
                    context="Paris",
                )
                for i in range(block, min(total, block + 20))
            ]
            logical_cases.extend(rows)
            dataset, _ = await database.create_dataset(
                DatasetCreate(name=f"process-benchmark-{identity}-{block}", version="1", cases=rows)
            )
            run_ids.append(
                await queue.submit(
                    RunCreate(dataset_id=dataset.id), provider, f"{identity}-{block}"
                )
            )
        for index in range(workers):
            await launch(index)
        ready = [await wait_file(control / f"ready-{i}-0.json") for i in range(workers)]
        if len({r["pid"] for r in ready}) != workers:
            raise RuntimeError("Worker processes are not independent")
        before, _ = await pg_stats(database)
        if config["diagnostics"]:
            wal_samples.append(await wal_snapshot(database))
        started = perf_counter()
        (control / "start.json").write_text(json.dumps({"time": started}))
        monitor_task = asyncio.create_task(monitor())
        restarted = False
        handled_exits = set()
        async with asyncio.timeout(900):
            while True:
                for process, index, generation in list(processes):
                    if process.returncode is not None and process.pid not in handled_exits:
                        handled_exits.add(process.pid)
                        if scenario == "recovery" and process.returncode == 86 and not restarted:
                            restarted = True
                            await launch(index, 1)
                        else:
                            raise RuntimeError(
                                f"Unexpected worker process exit: {process.returncode}"
                            )
                async with database.sessions() as session:
                    completed = await session.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(Job.run_id.in_(run_ids), Job.status == "COMPLETED")
                    )
                    failed = await session.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(Job.run_id.in_(run_ids), Job.status == "FAILED")
                    )
                if failed:
                    raise RuntimeError("Benchmark exhausted job attempts")
                if completed == total:
                    break
                await asyncio.sleep(0.05)
        duration = perf_counter() - started
        (control / "stop").touch()
        await asyncio.gather(*(asyncio.wait_for(p.wait(), 20) for p, _, _ in processes))
        if any(p.returncode not in (0, 86) for p, _, _ in processes):
            raise RuntimeError("Worker failed while shutting down")
        monitor_stop.set()
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
        after, _ = await pg_stats(database)
        if config["diagnostics"]:
            wal_samples.append(await wal_snapshot(database))
        events = []
        for path in control.glob("trace-*.jsonl"):
            events.extend(json.loads(line) for line in path.read_text().splitlines())
        accepted = [e for e in events if e["kind"] == "accepted"]
        if len(accepted) != total or len({e["job_id"] for e in accepted}) != total:
            raise RuntimeError("Accepted trace does not match committed results")
        async with database.sessions() as session:
            jobs = (
                await session.execute(select(Job.id, Job.attempts).where(Job.run_id.in_(run_ids)))
            ).all()
            result_count = await session.scalar(
                select(func.count()).select_from(Result).where(Result.run_id.in_(run_ids))
            )
        if result_count != total:
            raise RuntimeError("Result count mismatch")
        operations = [e for e in events if e["kind"] == "provider-operation"]
        intervals = [
            (e["start"], e["end"])
            for e in events
            if e["kind"] in ("evaluation", "failed-evaluation")
        ]
        peak = overlap(intervals)
        if peak > workers:
            raise RuntimeError("Active evaluation bound exceeded")
        exits = [json.loads(p.read_text()) for p in control.glob("exit-*.json")]
        crash = (
            json.loads((control / "crash.json").read_text())
            if (control / "crash.json").exists()
            else None
        )
        recovered = next((e for e in accepted if crash and e["job_id"] == crash["job_id"]), None)
        effects = []
        for path in control.glob("effects-*.jsonl"):
            effects.extend(json.loads(line) for line in path.read_text().splitlines())
        output = dict(
            scenario=scenario,
            repetition=rep,
            worker_processes=workers,
            slots_per_process=1,
            initial_process_ids=[r["pid"] for r in ready],
            replaced_processes=int(restarted),
            model_tag=model,
            jobs_completed=total,
            workload_sha256=hashlib.sha256(
                json.dumps(logical_cases, sort_keys=True).encode()
            ).hexdigest(),
            duration_seconds=duration,
            throughput_jobs_per_second=total / duration,
            max_active_evaluations=peak,
            provider_requests=len(operations),
            retry_count=sum(a - 1 for _, a in jobs),
            terminal_job_error_rate=0,
            recovery_seconds=recovered["completed_at"] - crash["time"] if recovered else None,
            recovery_clock="after response/pre-ack crash marker to accepted replacement result",
            external_effects_for_crashed_job=sum(e["job_id"] == crash["job_id"] for e in effects)
            if crash
            else None,
            completion_latency_ms=distribution(
                [(e["completed_at"] - started) * 1000 for e in accepted]
            ),
            execution_latency_ms=distribution([e["execution_ms"] for e in accepted]),
            claim_latency_from_start_ms=distribution(
                [(e["claimed_at"] - started) * 1000 for e in accepted]
            ),
            provider_request_latency_ms=distribution(
                [(e["end"] - e["start"]) * 1000 for e in operations]
            ),
            postgres=dict(
                counter_deltas={k: after[k] - before[k] for k in before},
                sampled_peak_connections=max(s["connections"] for s in db_samples),
                sampled_peak_lock_waiters=max(s["lock_waiters"] for s in db_samples),
                samples=len(db_samples),
                container_samples=docker_samples,
            ),
            worker_lifetime_cpu_seconds=sum(e["cpu_seconds"] for e in exits),
            peak_worker_rss_kib=max(e["rss_kib"] for e in exits),
            diagnostics=dict(
                enabled=config["diagnostics"],
                lock_samples=lock_samples,
                wal_samples=wal_samples,
                worker_events=[e for e in events if e["kind"] == "worker-event"],
                sql_operations=[e for e in events if e["kind"] == "sql-operation"],
                event_loop_samples=[e for e in events if e["kind"] == "event-loop-delay"],
                run_lock_transactions=[e for e in events if e["kind"] == "run-lock-transaction"],
            ),
            simulated=True,
            response_cache_enabled=False,
            billable_token_usage=None,
            policy=config,
            raw_jobs=accepted,
        )
        succeeded = True
        return output
    finally:
        (control / "stop").touch()
        if monitor_task:
            monitor_task.cancel()
            await asyncio.gather(monitor_task, return_exceptions=True)
        for process, _, _ in processes:
            if process.returncode is None:
                process.kill()
        await asyncio.gather(*(p.wait() for p, _, _ in processes), return_exceptions=True)
        for log in logs:
            log.close()
        if not succeeded:
            # Include admissions with a lost caller acknowledgment; model is unique to this experiment.
            async with database.sessions() as session:
                run_ids = (await session.scalars(select(Run.id).where(Run.model == model))).all()
            for run_id in run_ids:
                await queue.cancel(run_id)


async def experiment(args, url):
    database = Database(url, pool_size=2)
    report = dict(
        kind="postgres-independent-process-worker-sweep",
        python=platform.python_version(),
        platform=platform.platform(),
        logical_cpus=os.cpu_count(),
        container_cpu_quota=Path("/sys/fs/cgroup/cpu.max").read_text().strip()
        if Path("/sys/fs/cgroup/cpu.max").exists()
        else None,
        container_memory_limit=Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if Path("/sys/fs/cgroup/memory.max").exists()
        else None,
        source_sha256={
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in (
                "jobs.py",
                "worker.py",
                "platform_actor.py",
                "platform_benchmark.py",
                "diagnostics.py",
                "database.py",
            )
        },
        jobs_per_throughput_variant=args.jobs,
        repetitions=args.repetitions,
        worker_levels=args.workers,
        simulated=True,
        response_cache_enabled=False,
        results=[],
    )
    try:
        await database.check_ready()
        async with database.sessions() as session:
            report["postgresql"] = await session.scalar(text("SELECT version()"))
            report["track_io_timing"] = await session.scalar(text("SHOW track_io_timing"))
            active = await session.scalar(
                select(func.count()).select_from(Job).where(Job.status.in_(("PENDING", "RUNNING")))
            )
        if active:
            raise RuntimeError(
                "Inspect unfinished benchmark work before starting another experiment"
            )
        order = list(args.workers)
        for rep in range(1, args.repetitions + 1):
            # Rotate order to reduce fixed sequential-first bias; retain exact order.
            sequence = order[(rep - 1) % len(order) :] + order[: (rep - 1) % len(order)]
            for workers in sequence:
                result = await variant(database, args, workers, rep, "throughput")
                report["results"].append(result)
                Path(args.output).write_text(json.dumps(report, indent=2, default=float) + "\n")
                print(
                    json.dumps(
                        {
                            k: result[k]
                            for k in (
                                "scenario",
                                "repetition",
                                "worker_processes",
                                "jobs_completed",
                                "duration_seconds",
                                "max_active_evaluations",
                            )
                        }
                    ),
                    flush=True,
                )
        if not args.skip_recovery:
            for workers in order:
                result = await variant(database, args, workers, 1, "recovery")
                report["results"].append(result)
                Path(args.output).write_text(json.dumps(report, indent=2, default=float) + "\n")
                print(
                    json.dumps(
                        {
                            k: result[k]
                            for k in (
                                "scenario",
                                "worker_processes",
                                "recovery_seconds",
                                "external_effects_for_crashed_job",
                            )
                        }
                    ),
                    flush=True,
                )
        report["summary"] = {
            str(n): {
                "mean_duration_seconds": statistics.mean(
                    r["duration_seconds"]
                    for r in report["results"]
                    if r["scenario"] == "throughput" and r["worker_processes"] == n
                ),
                "mean_throughput": statistics.mean(
                    r["throughput_jobs_per_second"]
                    for r in report["results"]
                    if r["scenario"] == "throughput" and r["worker_processes"] == n
                ),
            }
            for n in order
        }
        report["complete"] = True
        Path(args.output).write_text(json.dumps(report, indent=2, default=float) + "\n")
    finally:
        await database.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 4, 8, 16])
    parser.add_argument("--latency", type=float, default=0.005)
    parser.add_argument("--failure-every", type=int, default=97)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-recovery", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--postgres-container")
    parser.add_argument("--output", default="reports/platform-benchmark.json")
    args = parser.parse_args()
    if (
        not 1 <= args.jobs <= 1000
        or not 1 <= args.repetitions <= 5
        or not args.workers
        or len(set(args.workers)) != len(args.workers)
        or any(n not in (1, 4, 8, 16) for n in args.workers)
        or not 0 < args.latency <= 1
        or args.failure_every < 0
    ):
        parser.error("Invalid bounded benchmark configuration")
    if args.postgres_container and not re.fullmatch(r"[A-Za-z0-9_.-]+", args.postgres_container):
        parser.error("Invalid container name")
    url = os.environ.get("AGENTEVAL_BENCHMARK_DATABASE_URL")
    if not url or not make_url(url).database.endswith("_benchmark"):
        parser.error("A dedicated *_benchmark database is required")
    env = {**os.environ, "AGENTEVAL_DATABASE_URL": url, "AGENTEVAL_MIGRATION_DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        check=True,
        capture_output=True,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(experiment(args, url))


if __name__ == "__main__":
    main()
