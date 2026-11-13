"""Synthetic providers: verify durable queue transitions cannot bypass SDK admission."""

import hashlib
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, update

from agenteval.jobs import JobQueue
from agenteval.models import Job
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider, ProviderError
from agenteval.server_budget import BudgetProvider, ServerBudget, configure
from agenteval.worker import run_once

pytestmark = pytest.mark.integration


async def dataset(db):
    saved, _ = await db.create_dataset(
        DatasetCreate(
            name="synthetic-budget-queue",
            version="1",
            cases=[
                dict(
                    external_id="one", question="Capital?", expected_answer="Paris", context="Paris"
                )
            ],
        )
    )
    return RunCreate(dataset_id=saved.id)


async def test_exhaustion_between_generation_and_judgment_persists_failure_without_refund(
    db, tmp_path
):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 1, 100, 1)
    inner = FakeProvider()
    inner.generate = AsyncMock(wraps=inner.generate)
    inner.judge = AsyncMock(wraps=inner.judge)
    provider = BudgetProvider(inner, budget)
    queue, data = JobQueue(db), await dataset(db)
    run_id = await queue.submit(data, provider, "same-submission")
    assert await run_once(queue, provider, "synthetic-worker")
    run = await db.get_run(run_id)
    assert run.status == "FAILED" and not run.results
    job = (await queue.list_jobs(run_id))[0]
    assert job.status == "FAILED" and job.attempts == 1
    assert job.last_error == "provider_budget_exhausted"
    inner.generate.assert_awaited_once()
    inner.judge.assert_not_awaited()
    assert await queue.submit(data, provider, "same-submission") == run_id
    assert not await run_once(
        queue, BudgetProvider(FakeProvider(), ServerBudget(path)), "restarted-worker"
    )
    assert ServerBudget(path).status()["attempts_reserved"] == 1


async def test_uncertain_attempt_blocks_retry_even_after_worker_provider_restart(db, tmp_path):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 10, 100, 1)
    inner = FakeProvider()
    inner.generate = AsyncMock(side_effect=ProviderError("unavailable", True))
    provider = BudgetProvider(inner, budget)
    queue = JobQueue(db)
    run_id = await queue.submit(await dataset(db), provider, "uncertain-submission", max_attempts=2)
    assert await run_once(queue, provider, "first-worker")
    job = (await queue.list_jobs(run_id))[0]
    assert job.status == "PENDING" and job.last_error == "unavailable"
    assert budget.status()["active_or_uncertain"] == 1
    # Advance only this dedicated test job's retry eligibility, avoiding a wall-clock sleep.
    async with db.sessions.begin() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(available_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    replacement = FakeProvider()
    replacement.generate = AsyncMock(wraps=replacement.generate)
    assert await run_once(
        queue, BudgetProvider(replacement, ServerBudget(path)), "replacement-worker"
    )
    replacement.generate.assert_not_awaited()
    inner.generate.assert_awaited_once()
    final = (await queue.list_jobs(run_id))[0]
    assert (
        final.status == "FAILED" and final.attempts == 2 and final.last_error == "provider_capacity"
    )
    assert (await db.get_run(run_id)).status == "FAILED"
    assert budget.status()["attempts_reserved"] == 1
    assert budget.status()["active_or_uncertain"] == 1


class VersionedStub(FakeProvider):
    model = "synthetic-versioned-budget-provider"

    def __init__(self, version, calls):
        self.judge_prompt_version = version
        self.judge_prompt_sha256 = hashlib.sha256(version.encode()).hexdigest()
        self.calls = calls

    def with_judge_prompt(self, version):
        return VersionedStub(version, self.calls)

    async def generate(self, data):
        self.calls.append(("generate", self.judge_prompt_version))
        return await super().generate(data)

    async def judge(self, data):
        self.calls.append(("judge", self.judge_prompt_version))
        return await super().judge(data)


async def test_prompt_snapshot_rebinding_keeps_the_shared_budget(db, tmp_path):
    budget = configure(tmp_path / "budget.sqlite3", 2, 100, 1)
    calls = []
    queue, data = JobQueue(db), await dataset(db)
    submitted = BudgetProvider(VersionedStub("candidate-v2", calls), budget)
    run_id = await queue.submit(data, submitted, "versioned-submission")
    worker = BudgetProvider(VersionedStub("v1", calls), budget)
    assert await run_once(queue, worker, "different-default-worker")
    run = await db.get_run(run_id)
    assert run.status == "COMPLETED" and len(run.results) == 1
    assert run.results[0].judge_prompt_version == "candidate-v2"
    assert run.results[0].judge_prompt_sha256 == submitted.judge_prompt_sha256
    assert calls == [("generate", "candidate-v2"), ("judge", "candidate-v2")]
    assert budget.status()["attempts_reserved"] == 2
    later = await queue.submit(data, worker, "new-submission")
    assert await run_once(queue, worker, "same-budget-worker")
    assert (await db.get_run(later)).status == "FAILED"
    assert len(calls) == 2
