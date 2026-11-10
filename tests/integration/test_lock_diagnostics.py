"""Observe actual PostgreSQL blockers and attribute the timed-out SQL operation."""

import asyncio
import io
import json
from time import perf_counter

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from agenteval.diagnostics import instrument_sql, lock_snapshot
from agenteval.jobs import JobQueue
from agenteval.models import Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider

pytestmark = pytest.mark.integration


async def test_lock_graph_attributes_run_lock_timeout_without_query_text(db):
    trace = io.StringIO()
    instrument_sql(db, trace)
    dataset, _ = await db.create_dataset(
        DatasetCreate(
            name="diagnostics",
            version="1",
            cases=[
                dict(
                    external_id="one", question="private question", expected_answer="private answer"
                )
            ],
        )
    )
    run_id = await JobQueue(db).submit(
        RunCreate(dataset_id=dataset.id), FakeProvider(), "diagnostic"
    )

    async def waiter():
        async with db.sessions.begin() as session:
            await session.execute(text("SET LOCAL statement_timeout = '1500ms'"))
            await session.execute(select(Run).where(Run.id == run_id).with_for_update())

    async with db.sessions.begin() as blocker:
        blocker_pid = await blocker.scalar(text("SELECT pg_backend_pid()"))
        await blocker.execute(select(Run).where(Run.id == run_id).with_for_update())
        task = asyncio.create_task(waiter())
        try:
            async with asyncio.timeout(3):
                while True:
                    snapshots = await lock_snapshot(db)
                    if any(blocker_pid in row["blockers"] for row in snapshots):
                        observed_at = perf_counter()
                        break
                    await asyncio.sleep(0.01)
            with pytest.raises(DBAPIError):
                await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    records = [json.loads(line) for line in trace.getvalue().splitlines()]
    errors = [r for r in records if r.get("operation") == "run_lock" and r["error_type"]]
    assert len(errors) == 1 and errors[0]["sqlstate"] == "57014"
    assert errors[0]["start"] <= observed_at <= errors[0]["end"]
    assert errors[0]["backend_pid"] in {
        row["pid"] for row in snapshots if blocker_pid in row["blockers"]
    }
    transactions = [r for r in records if r["kind"] == "run-lock-transaction"]
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction["backend_pid"] == blocker_pid and transaction["outcome"] == "commit"
    assert transaction["lock_returned"] <= observed_at <= transaction["transaction_end_started"]
    assert "private question" not in trace.getvalue() and "private answer" not in trace.getvalue()
    assert all("query" not in row for row in snapshots)
