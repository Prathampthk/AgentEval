"""Deterministic workloads with a real PostgreSQL queue, no external API calls."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from agenteval.jobs import JobQueue
from agenteval.models import Job
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider, ProviderError
from agenteval.service import evaluate as real_evaluate
from agenteval.worker import WorkerMetrics, run_once, serve

pytestmark = pytest.mark.integration


def cases(count):
    return [
        {"external_id": str(i), "question": str(i), "expected_answer": "Paris", "context": "Paris"}
        for i in range(count)
    ]


async def submit(db, name, count, **policy):
    dataset, _ = await db.create_dataset(DatasetCreate(name=name, version="1", cases=cases(count)))
    queue = JobQueue(db)
    run_id = await queue.submit(RunCreate(dataset_id=dataset.id), FakeProvider(), name, **policy)
    return queue, run_id


async def until(predicate, timeout=15):
    async with asyncio.timeout(timeout):
        while not await predicate():
            await asyncio.sleep(0.01)


async def terminal(db, run_id):
    return (await db.get_run(run_id)).status != "RUNNING"


def named(owner):
    return [
        task for task in asyncio.all_tasks() if task.get_name().startswith(f"agenteval:{owner}:")
    ]


async def test_sixteen_overlap_with_bounded_tasks_and_no_queue_prefetch(db, monkeypatch):
    dataset, _ = await db.create_dataset(
        DatasetCreate(name="bounded", version="1", cases=cases(20))
    )
    queue = JobQueue(db)
    runs = [
        await queue.submit(RunCreate(dataset_id=dataset.id), FakeProvider(), f"bounded-{i}")
        for i in range(6)
    ]  # 120 jobs: greater than the allowed live-task bound.
    gate = asyncio.Event()
    full = asyncio.Event()
    active = peak = executed = 0

    class Controlled(FakeProvider):
        async def generate(self, data):
            await gate.wait()
            return await super().generate(data)

    async def measured(*args, **kwargs):
        nonlocal active, peak, executed
        active += 1
        executed += 1
        peak = max(peak, active)
        if active == 16:
            full.set()
        try:
            return await real_evaluate(*args, **kwargs)
        finally:
            active -= 1

    monkeypatch.setattr("agenteval.worker.evaluate", measured)
    stop = asyncio.Event()
    metrics = WorkerMetrics()
    baseline = len(asyncio.all_tasks())
    pool = asyncio.create_task(
        serve(
            stop, queue, Controlled(), "bounded", concurrency=16, poll_seconds=0.01, metrics=metrics
        )
    )
    try:
        await asyncio.wait_for(full.wait(), 10)
        assert active == peak == 16  # Proves actual evaluate calls overlap, not just claimed rows.
        assert len(named("bounded")) <= 4 * 16 + 1
        assert len(asyncio.all_tasks()) <= baseline + 4 * 16 + 6
        async with db.sessions() as session:
            counts = dict(
                (await session.execute(select(Job.status, func.count()).group_by(Job.status))).all()
            )
        assert counts == {"PENDING": 104, "RUNNING": 16}
        gate.set()
        for run_id in runs:
            await until(lambda: terminal(db, run_id))
        stop.set()
        await asyncio.wait_for(pool, 5)
        assert executed == 120 and active == 0
        assert peak <= 16 and peak > 1
        assert metrics.max_active_evaluations == peak
        assert metrics.attempts_started == 120 and metrics.active_evaluations == 0
        assert not named("bounded")
        for run_id in runs:
            assert (await db.get_run(run_id)).status == "COMPLETED"
    finally:
        gate.set()
        stop.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)


async def test_graceful_stop_drains_active_jobs_and_preserves_pending_work(db):
    queue, run_id = await submit(db, "drain", 5)
    entered = asyncio.Event()
    release = asyncio.Event()
    active = 0

    class Controlled(FakeProvider):
        async def generate(self, data):
            nonlocal active
            active += 1
            if active == 2:
                entered.set()
            await release.wait()
            return await super().generate(data)

    stop = asyncio.Event()
    pool = asyncio.create_task(
        serve(
            stop, queue, Controlled(), "drain", concurrency=2, poll_seconds=0.01, shutdown_seconds=2
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        stop.set()
        release.set()
        metrics = await asyncio.wait_for(pool, 5)
        jobs = await queue.list_jobs(run_id)
        assert sum(job.status == "COMPLETED" for job in jobs) == 2
        assert sum(job.status == "PENDING" and job.attempts == 0 for job in jobs) == 3
        assert metrics.active_evaluations == 0 and metrics.attempts_started == 2
        assert not named("drain")
        for _ in range(3):
            assert await run_once(queue, FakeProvider(), "replacement")
        assert (await db.get_run(run_id)).status == "COMPLETED"
    finally:
        stop.set()
        release.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)


async def test_drain_deadline_cancels_tasks_without_losing_leased_jobs(db):
    queue, run_id = await submit(db, "deadline", 2)
    started = asyncio.Event()
    active = canceled = 0

    class Blocking(FakeProvider):
        async def generate(self, data):
            nonlocal active, canceled
            active += 1
            if active == 2:
                started.set()
            try:
                await asyncio.Event().wait()
            finally:
                canceled += 1

    stop = asyncio.Event()
    pool = asyncio.create_task(
        serve(stop, queue, Blocking(), "deadline", concurrency=2, shutdown_seconds=0.02)
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        stop.set()
        metrics = await asyncio.wait_for(pool, 5)
        assert canceled == 2 and metrics.active_evaluations == 0
        assert not named("deadline")
        assert all(job.status == "RUNNING" for job in await queue.list_jobs(run_id))
        assert (await db.get_run(run_id)).results == []
        async with db.sessions.begin() as session:
            await session.execute(
                update(Job)
                .where(Job.run_id == run_id)
                .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
            )
        assert await queue.recover() == 2
        for _ in range(2):
            assert await run_once(queue, FakeProvider(), "replacement")
        assert (await db.get_run(run_id)).status == "COMPLETED"
    finally:
        stop.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)


async def test_failure_and_timeout_do_not_stop_other_jobs(db):
    queue, run_id = await submit(db, "failures", 8, max_attempts=1, job_timeout=0.05)

    class Failing(FakeProvider):
        async def generate(self, data):
            if data.question == "0":
                raise ProviderError("authentication", False)
            if data.question == "1":
                await asyncio.Event().wait()
            return await super().generate(data)

    stop = asyncio.Event()
    pool = asyncio.create_task(
        serve(stop, queue, Failing(), "failures", concurrency=3, poll_seconds=0.01)
    )
    try:
        await until(lambda: terminal(db, run_id))
        stop.set()
        metrics = await asyncio.wait_for(pool, 5)
        run = await db.get_run(run_id)
        assert run.status == "FAILED" and len(run.results) == 6
        jobs = await queue.list_jobs(run_id)
        assert {j.last_error for j in jobs if j.status == "FAILED"} == {
            "authentication",
            "job_timeout",
        }
        assert metrics.attempts_started == 8 and metrics.active_evaluations == 0
        assert metrics.max_active_evaluations <= 3
        assert not named("failures")
    finally:
        stop.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)


async def test_cancelled_evaluation_frees_lane_for_next_run(db):
    queue, canceled_run = await submit(db, "cancel-slot", 1)
    _, next_run = await submit(db, "next-slot", 1)
    entered = asyncio.Event()
    canceled = asyncio.Event()
    calls = 0

    class FirstBlocks(FakeProvider):
        async def generate(self, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    canceled.set()
            return await super().generate(data)

    stop = asyncio.Event()
    pool = asyncio.create_task(
        serve(
            stop,
            queue,
            FirstBlocks(),
            "cancel-slot",
            concurrency=1,
            poll_seconds=0.01,
            lease_seconds=1,
            heartbeat_seconds=0.02,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await queue.cancel(canceled_run)
        await until(lambda: terminal(db, next_run))
        stop.set()
        metrics = await asyncio.wait_for(pool, 5)
        assert canceled.is_set() and calls == 2
        assert (await db.get_run(canceled_run)).status == "CANCELED"
        assert (await db.get_run(next_run)).status == "COMPLETED"
        assert metrics.max_active_evaluations == 1 and metrics.active_evaluations == 0
        assert not named("cancel-slot")
    finally:
        stop.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)


async def test_shutdown_during_claim_does_not_start_provider_work(db):
    queue, run_id = await submit(db, "claim-race", 1)
    committed = asyncio.Event()
    release = asyncio.Event()
    original = queue.claim

    async def delayed_claim(*args, **kwargs):
        claim = await original(*args, **kwargs)
        committed.set()
        await release.wait()
        return claim

    queue.claim = delayed_claim
    stop = asyncio.Event()
    pool = asyncio.create_task(serve(stop, queue, FakeProvider(), "claim-race", shutdown_seconds=2))
    try:
        await asyncio.wait_for(committed.wait(), 5)
        stop.set()
        release.set()
        metrics = await asyncio.wait_for(pool, 5)
        assert metrics.attempts_started == 0
        assert (await queue.list_jobs(run_id))[0].status == "RUNNING"
        assert (await db.get_run(run_id)).results == []
        assert not named("claim-race")
    finally:
        stop.set()
        release.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)
