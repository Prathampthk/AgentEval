import asyncio
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from agenteval.api import create_app
from agenteval.database import DatasetConflict, RunConflict
from agenteval.models import Dataset, Result
from agenteval.models import TestCase as CaseModel
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.persistent_runs import execute_run
from agenteval.providers import FakeProvider, ProviderError

pytestmark = pytest.mark.integration
DATASET = {
    "name": "geography",
    "version": "1",
    "cases": [
        {
            "external_id": "france",
            "question": "Capital of France?",
            "expected_answer": "Paris",
            "context": "Paris",
            "exact_match": True,
        },
        {
            "external_id": "uk",
            "question": "Capital of UK?",
            "expected_answer": "London",
            "context": "London",
            "exact_match": True,
        },
    ],
}


async def test_dataset_concurrent_creation_and_conflicting_version(db):
    outputs = await asyncio.gather(*(db.create_dataset(DatasetCreate(**DATASET)) for _ in range(5)))
    assert len({item[0].id for item in outputs}) == 1
    assert sum(item[1] for item in outputs) == 1
    reversed_data = {**DATASET, "cases": list(reversed(DATASET["cases"]))}
    same, created = await db.create_dataset(DatasetCreate(**reversed_data))
    assert not created and same.id == outputs[0][0].id
    with pytest.raises(DatasetConflict):
        await db.create_dataset(
            DatasetCreate(
                **{**DATASET, "cases": [{**DATASET["cases"][0], "expected_answer": "wrong"}]}
            )
        )
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Dataset)) == 1
        assert await session.scalar(select(func.count()).select_from(CaseModel)) == 2


async def test_run_roundtrip_and_terminal_guard(db):
    dataset, _ = await db.create_dataset(DatasetCreate(**DATASET))
    run = await execute_run(RunCreate(dataset_id=dataset.id), db, FakeProvider(), 1)
    assert run.status == "COMPLETED"
    assert len(run.results) == 2 and all(result.passed for result in run.results)
    assert run.created_at.tzinfo is not None and run.completed_at.tzinfo is not None
    assert run.results[0].generation_usage.input_tokens is None
    assert run.configuration["provider_timeout_seconds"] == 1
    with pytest.raises(RunConflict):
        await db.finish_run(run.id, run.results)
    await db.fail_run(run.id, "late_failure")
    assert (await db.get_run(run.id)).status == "COMPLETED"


async def test_partial_provider_failure_saves_failed_run_without_partial_results(db):
    class FailSecond(FakeProvider):
        calls = 0

        async def generate(self, data):
            self.calls += 1
            if self.calls == 2:
                raise ProviderError("rate_limit", True)
            return await super().generate(data)

    dataset, _ = await db.create_dataset(DatasetCreate(**DATASET))
    run = await execute_run(RunCreate(dataset_id=dataset.id), db, FailSecond(), 1)
    assert run.status == "FAILED"
    assert run.error_category == "rate_limit"
    assert run.results == [] and run.completed_at is not None


async def test_result_failure_rolls_back_completion_and_all_results(db):
    dataset, _ = await db.create_dataset(DatasetCreate(**DATASET))
    good = await execute_run(RunCreate(dataset_id=dataset.id), db, FakeProvider(), 1)
    run_id = await db.start_run(dataset.id, FakeProvider(), {})
    results = [r.model_copy(deep=True) for r in good.results]
    # Bypass Pydantic to prove the actual database protects the score invariant.
    results[1].judgment.correctness = 99
    with pytest.raises(IntegrityError):
        await db.finish_run(run_id, results)
    after = await db.get_run(run_id)
    assert after.status == "RUNNING" and after.results == []
    async with db.sessions() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(Result).where(Result.run_id == run_id)
            )
            == 0
        )


async def test_results_cannot_reference_another_dataset(db):
    first, _ = await db.create_dataset(DatasetCreate(**DATASET))
    second, _ = await db.create_dataset(DatasetCreate(**{**DATASET, "version": "2"}))
    good = await execute_run(RunCreate(dataset_id=first.id), db, FakeProvider(), 1)
    async with db.sessions() as session:
        original = await session.scalar(select(Result).where(Result.run_id == good.id))
        values = {
            column.name: getattr(original, column.name) for column in Result.__table__.columns
        }
    other_run = await db.start_run(second.id, FakeProvider(), {})
    values.update(id=uuid4(), run_id=other_run, dataset_id=second.id)
    with pytest.raises(IntegrityError) as caught:
        async with db.sessions.begin() as session:
            session.add(Result(**values))
    assert "fk_result_case" in str(caught.value.orig)


async def test_no_database_transaction_held_during_provider_call(db):
    class Inspect(FakeProvider):
        async def generate(self, data):
            async with db.sessions() as session:
                idle = await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND state = 'idle in transaction'"
                    )
                )
                assert idle == 0
            assert db.engine.pool.checkedout() == 0
            return await super().generate(data)

    dataset, _ = await db.create_dataset(DatasetCreate(**DATASET))
    assert (
        await execute_run(RunCreate(dataset_id=dataset.id), db, Inspect(), 1)
    ).status == "COMPLETED"


async def test_http_workflow_survives_new_application_instance(db, pg_url):
    app = create_app(FakeProvider(), database_url=pg_url)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/health/ready")).json()["database"] == "ready"
            response = await client.post("/datasets", json=DATASET)
            assert response.status_code == 201
            dataset = response.json()
            assert (await client.post("/datasets", json=DATASET)).status_code == 200
            conflict = await client.post(
                "/datasets", json={**DATASET, "cases": [DATASET["cases"][0]]}
            )
            assert conflict.status_code == 409
            response = await client.post("/runs", json={"dataset_id": dataset["id"]})
            assert response.status_code == 201
            run = response.json()
            assert run["status"] == "COMPLETED" and len(run["results"]) == 2
    restarted = create_app(FakeProvider(), database_url=pg_url)
    async with restarted.router.lifespan_context(restarted):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=restarted), base_url="http://test"
        ) as client:
            assert (await client.get(f"/runs/{run['id']}")).json() == run
            assert (await client.get(f"/datasets/{dataset['id']}")).json() == dataset
            listed = await client.get("/runs", params={"dataset_id": dataset["id"], "limit": 1})
            assert listed.json()[0]["id"] == run["id"]
            assert (await client.get(f"/runs/{uuid4()}")).status_code == 404
            assert (
                await client.post("/runs", json={"dataset_id": str(uuid4())})
            ).status_code == 404
            assert (
                await client.get("/runs", params={"dataset_id": dataset["id"], "limit": 101})
            ).status_code == 422


async def test_cancel_request_marks_failed_best_effort(db):
    started = asyncio.Event()

    class Wait(FakeProvider):
        async def generate(self, data):
            started.set()
            await asyncio.Event().wait()

    dataset, _ = await db.create_dataset(DatasetCreate(**DATASET))
    task = asyncio.create_task(execute_run(RunCreate(dataset_id=dataset.id), db, Wait(), 1))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    run = (await db.list_runs(dataset.id, 1))[0]
    assert run.status == "FAILED" and run.error_category == "request_canceled"


async def test_incomplete_results_and_incompatible_configuration_are_rejected(db):
    dataset, _ = await db.create_dataset(DatasetCreate(**DATASET))
    good = await execute_run(RunCreate(dataset_id=dataset.id), db, FakeProvider(), 1)
    pending = await db.start_run(dataset.id, FakeProvider(), {})
    with pytest.raises(ValueError, match="exactly one"):
        await db.finish_run(pending, good.results[:1])
    results = [r.model_copy(deep=True) for r in good.results]
    results[0].model = "different-model"
    with pytest.raises(ValueError, match="configuration"):
        await db.finish_run(pending, results)
    run = await db.get_run(pending)
    assert run.status == "RUNNING" and run.results == []


def test_migration_downgrade_upgrade_and_model_alignment(pg_url):
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "AGENTEVAL_DATABASE_URL": pg_url,
        "AGENTEVAL_MIGRATION_DATABASE_URL": pg_url,
    }
    # The pg_url fixture has already verified this is the dedicated *_test database.
    for args in (("downgrade", "base"), ("upgrade", "head"), ("upgrade", "head"), ("check",)):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
