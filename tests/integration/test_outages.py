"""Destructive connection interruption is restricted to the dedicated test DB."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from agenteval.jobs import JobQueue, LostLease
from agenteval.models import Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider
from agenteval.service import evaluate
from agenteval.worker import serve

pytestmark = pytest.mark.integration


async def setup(db):
    dataset, _ = await db.create_dataset(
        DatasetCreate(
            name="outage",
            version="1",
            cases=[
                {
                    "external_id": "one",
                    "question": "Capital?",
                    "expected_answer": "Paris",
                    "context": "Paris",
                }
            ],
        )
    )
    queue = JobQueue(db)
    run_id = await queue.submit(
        RunCreate(dataset_id=dataset.id),
        FakeProvider(),
        "outage",
        provider_timeout=3,
        job_timeout=5,
    )
    return queue, run_id


async def test_run_deadline_fences_late_results_and_cancels_pending_work(db):
    queue, run_id = await setup(db)
    claim = await queue.claim("worker", FakeProvider())
    result = await evaluate(claim.request, FakeProvider())
    async with db.sessions.begin() as session:
        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(deadline_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    assert not await queue.renew(claim)
    with pytest.raises(LostLease):
        await queue.complete(claim, result)
    await queue.recover()
    run = await db.get_run(run_id)
    assert run.status == "CANCELED" and run.error_category == "run_timeout" and run.results == []
    assert (await queue.list_jobs(run_id))[0].last_error == "run_timeout"
    assert await queue.claim("replacement", FakeProvider()) is None


async def test_database_refuses_connections_then_worker_recovers(db, pg_url):
    queue, run_id = await setup(db)
    parsed = make_url(pg_url)
    assert parsed.database.endswith("_test")
    control = create_async_engine(
        parsed.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    identifier = control.dialect.identifier_preparer.quote(parsed.database)
    entered, canceled = asyncio.Event(), asyncio.Event()
    calls = 0

    class Controlled(FakeProvider):
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
            Controlled(),
            "outage-worker",
            poll_seconds=0.02,
            lease_seconds=0.6,
            heartbeat_seconds=0.05,
        )
    )
    disabled = False
    try:
        await asyncio.wait_for(entered.wait(), 5)
        async with control.connect() as connection:
            await connection.execute(text(f"ALTER DATABASE {identifier} ALLOW_CONNECTIONS false"))
            disabled = True
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"
                ),
                {"name": parsed.database},
            )
        await asyncio.wait_for(canceled.wait(), 5)
        async with control.connect() as connection:
            await connection.execute(text(f"ALTER DATABASE {identifier} ALLOW_CONNECTIONS true"))
            disabled = False
        async with asyncio.timeout(10):
            while (await db.get_run(run_id)).status == "RUNNING":
                await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(pool, 5)
        run = await db.get_run(run_id)
        assert run.status == "COMPLETED" and len(run.results) == 1 and calls == 2
        assert (await queue.list_jobs(run_id))[0].attempts == 2
    finally:
        if disabled:
            async with control.connect() as connection:
                await connection.execute(
                    text(f"ALTER DATABASE {identifier} ALLOW_CONNECTIONS true")
                )
        stop.set()
        pool.cancel()
        await asyncio.gather(pool, return_exceptions=True)
        await control.dispose()
