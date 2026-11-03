"""Real PostgreSQL failure and concurrency tests for the durable queue."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from agenteval.api import create_app
from agenteval.database import Database, RunConflict
from agenteval.jobs import JobQueue, LostLease, QueueFull, SubmissionConflict
from agenteval.models import Job, Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider, ProviderError
from agenteval.service import evaluate
from agenteval.worker import run_once

pytestmark = pytest.mark.integration
DATASET = DatasetCreate(
    name="jobs",
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


async def submitted(db, **policy):
    dataset, _ = await db.create_dataset(DATASET)
    queue = JobQueue(db)
    run_id = await queue.submit(
        RunCreate(dataset_id=dataset.id), FakeProvider(), str(uuid4()), **policy
    )
    return queue, run_id


async def expire(db, claim):
    async with db.sessions.begin() as session:
        await session.execute(
            update(Job)
            .where(Job.id == claim.id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )


async def test_concurrent_idempotency_and_conflicting_payload(db):
    dataset, _ = await db.create_dataset(DATASET)
    data = RunCreate(dataset_id=dataset.id)
    queue = JobQueue(db)
    ids = await asyncio.gather(*(queue.submit(data, FakeProvider(), "same-key") for _ in range(5)))
    assert len(set(ids)) == 1
    with pytest.raises(SubmissionConflict):
        await queue.submit(
            RunCreate(dataset_id=dataset.id, prompt="different"), FakeProvider(), "same-key"
        )
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Run)) == 1
        assert await session.scalar(select(func.count()).select_from(Job)) == 1


async def test_two_workers_cannot_claim_same_job(db):
    queue, _ = await submitted(db)
    claims = await asyncio.gather(
        queue.claim("first", FakeProvider()), queue.claim("second", FakeProvider())
    )
    assert sum(claim is not None for claim in claims) == 1
    claim = next(claim for claim in claims if claim)
    assert claim.attempt == 1
    assert await queue.renew(claim)


async def test_admission_is_atomic_across_submissions(db):
    dataset, _ = await db.create_dataset(DATASET)
    queue = JobQueue(db)

    async def submit(key):
        try:
            return await queue.submit(
                RunCreate(dataset_id=dataset.id), FakeProvider(), key, capacity=1
            )
        except QueueFull:
            return None

    results = await asyncio.gather(submit("first"), submit("second"))
    assert sum(result is not None for result in results) == 1
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
    key = "first" if results[0] else "second"
    assert await queue.submit(
        RunCreate(dataset_id=dataset.id), FakeProvider(), key, capacity=1
    ) == next(r for r in results if r)


async def test_expired_claim_recovery_fences_old_worker(db):
    queue, run_id = await submitted(db)
    old = await queue.claim("old", FakeProvider())
    response = await evaluate(old.request, FakeProvider())
    await expire(db, old)
    assert not await queue.renew(old)
    assert await queue.recover() == 1
    new = await queue.claim("new", FakeProvider())
    assert new.token != old.token and new.attempt == 2
    with pytest.raises(LostLease):
        await queue.complete(old, response)
    with pytest.raises(LostLease):
        await queue.fail(old, "late_error", retryable=False)
    await queue.complete(new, response)
    run = await db.get_run(run_id)
    assert run.status == "COMPLETED" and len(run.results) == 1


async def test_crash_after_response_repeats_external_work_but_commits_once(db, pg_url):
    class Counting(FakeProvider):
        calls = 0

        async def generate(self, data):
            self.calls += 1
            return await super().generate(data)

    provider = Counting()
    queue, run_id = await submitted(db)
    dead = await queue.claim("crashed", provider)
    await evaluate(dead.request, provider)  # Response received, deliberately not persisted.
    await expire(db, dead)
    fresh_database = Database(pg_url)
    try:
        fresh = JobQueue(fresh_database)
        assert await fresh.recover() == 1
        assert await run_once(fresh, provider, "restarted")
    finally:
        await fresh_database.close()
    assert provider.calls == 2
    run = await db.get_run(run_id)
    assert run.status == "COMPLETED" and len(run.results) == 1


async def test_retry_exhaustion_and_terminal_immutability(db):
    queue, run_id = await submitted(db, max_attempts=2)
    first = await queue.claim("worker", FakeProvider())
    await queue.fail(first, "rate_limit", retryable=True)
    second = await queue.claim("worker", FakeProvider())
    assert second.attempt == 2
    await queue.fail(second, "rate_limit", retryable=True)
    assert await queue.claim("worker", FakeProvider()) is None
    job = (await queue.list_jobs(run_id))[0]
    assert job.status == "FAILED" and job.attempts == 2
    assert (await db.get_run(run_id)).status == "FAILED"
    with pytest.raises(LostLease):
        await queue.complete(second, await evaluate(second.request, FakeProvider()))
    await queue.cancel(run_id)
    assert (await queue.list_jobs(run_id))[0].status == "FAILED"


async def test_permanent_failure_does_not_retry_and_delay_persists(db):
    queue, run_id = await submitted(db)
    claim = await queue.claim("worker", FakeProvider())
    await queue.fail(claim, "authentication", retryable=False)
    assert (await queue.list_jobs(run_id))[0].attempts == 1
    assert (await db.get_run(run_id)).status == "FAILED"
    queue, waiting = await submitted(db)
    claim = await queue.claim("worker", FakeProvider())
    await queue.fail(claim, "rate_limit", retryable=True, delay_seconds=60)
    assert await JobQueue(db).claim("fresh-process", FakeProvider()) is None
    job = (await queue.list_jobs(waiting))[0]
    assert job.status == "PENDING" and job.last_error == "rate_limit" and job.attempts == 1
    await queue.cancel(waiting)
    assert (await queue.list_jobs(waiting))[0].status == "CANCELED"


async def test_cancel_running_prevents_late_completion(db):
    queue, run_id = await submitted(db)
    claim = await queue.claim("worker", FakeProvider())
    response = await evaluate(claim.request, FakeProvider())
    await queue.cancel(run_id)
    with pytest.raises(LostLease):
        await queue.complete(claim, response)
    assert not await queue.renew(claim)
    run = await db.get_run(run_id)
    assert run.status == "CANCELED" and run.results == []
    assert (await queue.list_jobs(run_id))[0].status == "CANCELED"


async def test_expired_last_attempt_fails_and_pending_cancel_is_terminal(db):
    queue, run_id = await submitted(db, max_attempts=1)
    claim = await queue.claim("worker", FakeProvider())
    await expire(db, claim)
    assert await queue.recover() == 1
    assert (await db.get_run(run_id)).status == "FAILED"
    queue, canceled = await submitted(db)
    await queue.cancel(canceled)
    assert await queue.claim("worker", FakeProvider()) is None
    assert (await db.get_run(canceled)).status == "CANCELED"


async def test_transaction_failure_rolls_back_job_completion_and_result(db):
    queue, run_id = await submitted(db)
    claim = await queue.claim("worker", FakeProvider())
    response = await evaluate(claim.request, FakeProvider())
    response.judgment.correctness = 99  # Prove the DB constraint, bypassing schema validation.
    with pytest.raises(IntegrityError):
        await queue.complete(claim, response)
    assert (await queue.list_jobs(run_id))[0].status == "RUNNING"
    assert (await db.get_run(run_id)).results == []


async def test_queued_run_cannot_be_completed_by_sync_path(db):
    queue, run_id = await submitted(db)
    with pytest.raises(RunConflict):
        await db.finish_run(run_id, [])
    await db.fail_run(run_id, "sync_failure")
    assert (await db.get_run(run_id)).status == "RUNNING"


async def test_provider_configuration_filters_claims(db):
    queue, _ = await submitted(db)
    other = FakeProvider()
    other.model = "another-model"
    assert await queue.claim("wrong-config", other) is None
    assert await queue.claim("correct-config", FakeProvider()) is not None


async def test_worker_permanent_provider_failure(db):
    class Invalid(FakeProvider):
        async def generate(self, data):
            raise ProviderError("invalid_output", False)

    queue, run_id = await submitted(db)
    assert await run_once(queue, Invalid(), "worker")
    assert (await db.get_run(run_id)).status == "FAILED"
    assert (await queue.list_jobs(run_id))[0].attempts == 1


async def test_http_submission_restart_and_worker_completion(db, pg_url):
    dataset, _ = await db.create_dataset(DATASET)
    app = create_app(FakeProvider(), database_url=pg_url)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            headers = {"Idempotency-Key": "http-key"}
            payload = {"dataset_id": str(dataset.id)}
            response = await client.post("/queued-runs", json=payload, headers=headers)
            assert response.status_code == 202
            run = response.json()
            assert run["execution_mode"] == "queued" and run["results"] == []
            assert (await client.post("/queued-runs", json=payload, headers=headers)).json()[
                "id"
            ] == run["id"]
            assert (
                await client.post(
                    "/queued-runs", json={**payload, "prompt": "changed"}, headers=headers
                )
            ).status_code == 409
            assert (await client.post("/queued-runs", json=payload)).status_code == 422
    fresh_database = Database(pg_url)
    try:
        assert await run_once(JobQueue(fresh_database), FakeProvider(), "restarted-worker")
    finally:
        await fresh_database.close()
    restarted = create_app(FakeProvider(), database_url=pg_url)
    async with restarted.router.lifespan_context(restarted):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=restarted), base_url="http://test"
        ) as client:
            completed = (await client.get("/runs/" + run["id"])).json()
            assert completed["status"] == "COMPLETED" and len(completed["results"]) == 1
            jobs = (await client.get("/runs/" + run["id"] + "/jobs")).json()
            assert jobs[0]["status"] == "COMPLETED" and jobs[0]["attempts"] == 1
            assert "lease_token" not in jobs[0]
            assert (await client.post("/runs/" + run["id"] + "/cancel")).json()[
                "status"
            ] == "COMPLETED"


async def test_heartbeat_renews_then_stops_execution_after_cancellation(db):
    queue, run_id = await submitted(db)
    renewed = asyncio.Event()
    provider_canceled = asyncio.Event()
    original = queue.renew

    async def observed_renew(claim, lease_seconds):
        result = await original(claim, lease_seconds)
        if result:
            renewed.set()
        return result

    queue.renew = observed_renew

    class Blocking(FakeProvider):
        async def generate(self, data):
            try:
                await asyncio.Event().wait()
            finally:
                provider_canceled.set()

    worker = asyncio.create_task(
        run_once(queue, Blocking(), "heartbeat-worker", lease_seconds=1, heartbeat_seconds=0.02)
    )
    try:
        await asyncio.wait_for(renewed.wait(), 2)
        await queue.cancel(run_id)
        assert await asyncio.wait_for(worker, 2)
        assert provider_canceled.is_set()
        assert (await db.get_run(run_id)).status == "CANCELED"
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


async def test_real_worker_process_exit_before_execution_recovers(db):
    import os
    import subprocess
    import sys

    queue, run_id = await submitted(db)
    child = """
import asyncio, os
from agenteval.database import Database
from agenteval.jobs import JobQueue
from agenteval.providers import FakeProvider
async def crash():
    db = Database(os.environ["AGENTEVAL_TEST_DATABASE_URL"])
    claim = await JobQueue(db).claim("crashing-process", FakeProvider())
    assert claim is not None
    os._exit(17)
asyncio.run(crash())
"""
    outcome = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", child],
        env=os.environ.copy(),
        capture_output=True,
        timeout=10,
    )
    assert outcome.returncode == 17
    job = (await queue.list_jobs(run_id))[0]
    assert job.status == "RUNNING" and job.attempts == 1
    async with db.sessions.begin() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    assert await queue.recover() == 1
    assert await run_once(queue, FakeProvider(), "replacement")
    assert (await db.get_run(run_id)).status == "COMPLETED"
    assert (await queue.list_jobs(run_id))[0].attempts == 2


async def test_competing_job_completions_preserve_run_aggregate(db):
    dataset, _ = await db.create_dataset(
        DatasetCreate(
            name="two-jobs",
            version="1",
            cases=[
                {
                    "external_id": str(i),
                    "question": "Capital?",
                    "expected_answer": "Paris",
                    "context": "Paris",
                }
                for i in range(2)
            ],
        )
    )
    queue = JobQueue(db)
    run_id = await queue.submit(RunCreate(dataset_id=dataset.id), FakeProvider(), "two-jobs")
    claims = await asyncio.gather(
        queue.claim("first", FakeProvider()), queue.claim("second", FakeProvider())
    )
    assert len({claim.id for claim in claims}) == 2
    responses = await asyncio.gather(*(evaluate(claim.request, FakeProvider()) for claim in claims))
    await asyncio.gather(
        *(queue.complete(claim, response) for claim, response in zip(claims, responses))
    )
    run = await db.get_run(run_id)
    assert run.status == "COMPLETED" and len(run.results) == 2


async def test_worker_retries_transient_failure_with_persisted_budget(db, monkeypatch):
    class Transient(FakeProvider):
        calls = 0

        async def generate(self, data):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError("rate_limit", True)
            return await super().generate(data)

    # Zero jitter removes wall-clock waiting without disabling the retry policy.
    monkeypatch.setattr("agenteval.worker.random.uniform", lambda low, high: 0)
    queue, run_id = await submitted(db)
    provider = Transient()
    assert await run_once(queue, provider, "first")
    assert (await queue.list_jobs(run_id))[0].status == "PENDING"
    assert await run_once(JobQueue(db), provider, "second")
    assert (await db.get_run(run_id)).status == "COMPLETED"
    assert (await queue.list_jobs(run_id))[0].attempts == 2
