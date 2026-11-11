"""Preserve historical prompt snapshots and reject cross-prompt result acceptance."""

import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from agenteval.jobs import JobQueue, SubmissionConflict
from agenteval.models import Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.persistent_runs import execute_run
from agenteval.providers import FakeProvider
from agenteval.service import evaluate
from agenteval.worker import run_once

pytestmark = pytest.mark.integration


class VersionedFixture(FakeProvider):
    model = "offline-prompt-provenance-fixture"

    def __init__(self, version):
        self.judge_prompt_version = version
        self.judge_prompt_sha256 = hashlib.sha256(version.encode()).hexdigest()

    def with_judge_prompt(self, version):
        return VersionedFixture(version)


async def dataset(db):
    saved, _ = await db.create_dataset(
        DatasetCreate(
            name="prompt-provenance",
            version="1",
            cases=[
                dict(
                    external_id="one", question="Capital?", expected_answer="Paris", context="Paris"
                )
            ],
        )
    )
    return RunCreate(dataset_id=saved.id)


@pytest.mark.parametrize("stored,current", [("v1", "candidate-v2"), ("candidate-v2", "v1")])
async def test_worker_executes_the_stored_prompt_after_configuration_change(db, stored, current):
    data = await dataset(db)
    queue = JobQueue(db)
    provider = VersionedFixture(stored)
    run_id = await queue.submit(data, provider, "prompt-snapshot")
    assert await run_once(queue, VersionedFixture(current), "versioned-worker")
    run = await db.get_run(run_id)
    assert run.status == "COMPLETED"
    assert run.configuration["judge_prompt_version"] == stored
    assert run.results[0].judge_prompt_version == stored
    assert run.results[0].judge_prompt_sha256 == provider.judge_prompt_sha256


async def test_wrong_prompt_result_rejected_before_persistence(db):
    queue = JobQueue(db)
    data = await dataset(db)
    provider = VersionedFixture("candidate-v2")
    run_id = await queue.submit(data, provider, "reject-wrong-prompt")
    claim = await queue.claim("worker", provider)
    result = await evaluate(claim.request, provider)
    with pytest.raises(ValueError, match="prompt version"):
        await queue.complete(claim, result.model_copy(update={"judge_prompt_version": "v1"}))
    with pytest.raises(ValueError, match="fingerprint"):
        await queue.complete(claim, result.model_copy(update={"judge_prompt_sha256": "wrong"}))
    assert not (await db.get_run(run_id)).results
    await queue.complete(claim, result)
    assert len((await db.get_run(run_id)).results) == 1


async def test_legacy_submission_replay_and_pending_job_survive_prompt_metadata_upgrade(db):
    data = await dataset(db)
    queue = JobQueue(db)
    legacy = VersionedFixture("v1")
    run_id = await queue.submit(data, legacy, "legacy-replay")
    async with db.sessions.begin() as session:
        run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
        config = dict(run.configuration)
        config.pop("judge_prompt_version")
        config.pop("judge_prompt_sha256")
        run.configuration = config
        original_identity = dict(
            dataset_id=str(run.dataset_id),
            configuration=config,
            provider=run.provider,
            model=run.model,
            simulated=run.simulated,
            rubric_version=run.rubric_version,
        )
        run.request_hash = hashlib.sha256(
            json.dumps(original_identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    assert await queue.submit(data, legacy, "legacy-replay") == run_id
    with pytest.raises(SubmissionConflict):
        await queue.submit(data, VersionedFixture("candidate-v2"), "legacy-replay")
    assert await run_once(queue, VersionedFixture("candidate-v2"), "upgraded-worker")
    run = await db.get_run(run_id)
    assert run.status == "COMPLETED" and run.results[0].judge_prompt_version == "v1"


async def test_sync_run_retains_prompt_metadata(db):
    provider = VersionedFixture("candidate-v2")
    run = await execute_run(await dataset(db), db, provider, 1)
    assert run.status == "COMPLETED"
    assert run.configuration["judge_prompt_version"] == "candidate-v2"
    assert run.results[0].judge_prompt_sha256 == provider.judge_prompt_sha256


async def test_changed_prompt_fingerprint_fails_before_provider_execution(db):
    data = await dataset(db)
    queue = JobQueue(db)
    run_id = await queue.submit(data, VersionedFixture("candidate-v2"), "changed-prompt")
    worker_provider = VersionedFixture("candidate-v2")
    worker_provider.judge_prompt_sha256 = "different-content"
    worker_provider.generate = AsyncMock()
    assert await run_once(queue, worker_provider, "incompatible-worker")
    worker_provider.generate.assert_not_awaited()
    run = await db.get_run(run_id)
    assert run.status == "FAILED" and not run.results
    assert (await queue.list_jobs(run_id))[0].last_error == "incompatible_judge_prompt"
