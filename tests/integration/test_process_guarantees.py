"""Real PG + independent interpreters, deterministic barriers and crash points."""

import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select, text, update

from agenteval.api import create_app
from agenteval.jobs import JobQueue, LostLease
from agenteval.models import Job, Run
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.providers import FakeProvider
from agenteval.service import evaluate

pytestmark = pytest.mark.integration
ACTOR = Path(__file__).resolve().parents[1] / "helpers/process_actor.py"


async def scenario(db):
    provider = FakeProvider()
    provider.model = "process-test-" + uuid4().hex[:12]
    dataset, _ = await db.create_dataset(
        DatasetCreate(
            name=provider.model,
            version="1",
            cases=[
                dict(
                    external_id="one", question="Capital?", expected_answer="Paris", context="Paris"
                )
            ],
        )
    )
    return provider, dataset, JobQueue(db)


async def launch(control, provider, index, action, **extra):
    arguments = [
        sys.executable,
        str(ACTOR),
        "--control",
        str(control),
        "--model",
        provider.model,
        "--index",
        str(index),
        "--action",
        action,
    ]
    for key, value in extra.items():
        arguments.extend(["--" + key, str(value)])
    return await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )


async def wait_file(path):
    async with asyncio.timeout(15):
        while not path.exists():
            await asyncio.sleep(0.01)
    return json.loads(path.read_text())


async def finish(process, expected=0):
    stdout, stderr = await asyncio.wait_for(process.communicate(), 15)
    assert process.returncode == expected, stderr.decode()[:1000]


async def cleanup(processes):
    for process in processes:
        if process.returncode is None:
            process.kill()
    await asyncio.gather(*(p.communicate() for p in processes), return_exceptions=True)


async def test_independent_process_duplicate_submissions(db, tmp_path):
    provider, dataset, queue = await scenario(db)
    processes = [
        await launch(tmp_path, provider, i, "submit", dataset=dataset.id, key=provider.model)
        for i in range(3)
    ]
    try:
        ready = [await wait_file(tmp_path / f"ready-{i}") for i in range(3)]
        assert len({r["pid"] for r in ready}) == 3
        (tmp_path / "go").touch()
        await asyncio.gather(*(finish(p) for p in processes))
        outputs = [await wait_file(tmp_path / f"result-{i}.json") for i in range(3)]
        assert len({r["run_id"] for r in outputs}) == 1
        async with db.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(Run)) == 1
            assert await session.scalar(select(func.count()).select_from(Job)) == 1
    finally:
        await cleanup(processes)


async def test_independent_process_atomic_claim(db, tmp_path):
    provider, dataset, queue = await scenario(db)
    await queue.submit(RunCreate(dataset_id=dataset.id), provider, provider.model)
    processes = [await launch(tmp_path, provider, i, "claim") for i in range(2)]
    try:
        for i in range(2):
            await wait_file(tmp_path / f"ready-{i}")
        (tmp_path / "go").touch()
        await asyncio.gather(*(finish(p) for p in processes))
        outputs = [await wait_file(tmp_path / f"result-{i}.json") for i in range(2)]
        assert len({r["pid"] for r in outputs}) == 2
        assert sum(r["claim"] is not None for r in outputs) == 1
    finally:
        await cleanup(processes)


@pytest.mark.parametrize("canceled", [False, True])
async def test_independent_stale_worker_cannot_complete(db, tmp_path, canceled):
    provider, dataset, queue = await scenario(db)
    run_id = await queue.submit(RunCreate(dataset_id=dataset.id), provider, provider.model)
    process = await launch(tmp_path, provider, "old", "hold")
    try:
        await wait_file(tmp_path / "ready-old")
        (tmp_path / "go").touch()
        await wait_file(tmp_path / "claimed-old")
        if canceled:
            await queue.cancel(run_id)
        else:
            async with db.sessions.begin() as session:
                await session.execute(
                    update(Job)
                    .where(Job.run_id == run_id)
                    .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
                )
            assert await queue.recover() == 1
            replacement = await queue.claim("replacement", provider)
        (tmp_path / "finish").touch()
        await finish(process)
        assert (await wait_file(tmp_path / "result-old.json"))["outcome"] == "LOST_LEASE"
        assert (await db.get_run(run_id)).results == []
        if not canceled:
            await queue.complete(replacement, await evaluate(replacement.request, provider))
            assert (await db.get_run(run_id)).status == "COMPLETED"
    finally:
        await cleanup([process])


@pytest.mark.parametrize("crash", ["before", "response", "ack"])
async def test_process_crash_delivery_boundaries(db, tmp_path, crash):
    provider, dataset, queue = await scenario(db)
    run_id = await queue.submit(RunCreate(dataset_id=dataset.id), provider, provider.model)
    process = await launch(tmp_path, provider, "crash", "crash-" + crash)
    processes = [process]
    try:
        await wait_file(tmp_path / "ready-crash")
        (tmp_path / "go").touch()
        await finish(process, 86)
        if crash == "ack":
            assert (await db.get_run(run_id)).status == "COMPLETED"
            assert await queue.claim("no-redelivery", provider) is None
        else:
            assert (await db.get_run(run_id)).results == []
            async with db.sessions.begin() as session:
                await session.execute(
                    update(Job)
                    .where(Job.run_id == run_id)
                    .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
                )
            assert await queue.recover() == 1
            replacement = await launch(tmp_path, provider, "replacement", "complete")
            processes.append(replacement)
            await finish(replacement)
        result = await db.get_run(run_id)
        assert result.status == "COMPLETED" and len(result.results) == 1
        effects = (tmp_path / "external-effects.jsonl").read_text().splitlines()
        assert len(effects) == (2 if crash == "response" else 1)
    finally:
        await cleanup(processes)


@pytest.mark.parametrize("operation", ["complete", "fail", "renew"])
async def test_expiry_rechecked_after_row_lock_wait(db, operation):
    provider, dataset, queue = await scenario(db)
    await queue.submit(RunCreate(dataset_id=dataset.id), provider, provider.model)
    claim = await queue.claim("expiry-test", provider, lease_seconds=2)
    response = await evaluate(claim.request, provider)
    async with db.sessions.begin() as blocker:
        await blocker.execute(select(Job).where(Job.id == claim.id).with_for_update())
        action = {
            "complete": lambda: queue.complete(claim, response),
            "fail": lambda: queue.fail(claim, "transient", retryable=True),
            "renew": lambda: queue.renew(claim),
        }[operation]
        task = asyncio.create_task(action())
        async with asyncio.timeout(5):
            while True:
                async with db.sessions() as observer:
                    waiting = await observer.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND pid<>pg_backend_pid()"
                        )
                    )
                if waiting:
                    break
                await asyncio.sleep(0.01)
            while True:
                async with db.sessions() as observer:
                    expired = await observer.scalar(
                        select(Job.lease_expires_at <= func.clock_timestamp()).where(
                            Job.id == claim.id
                        )
                    )
                if expired:
                    break
                await asyncio.sleep(0.01)
    if operation == "renew":
        assert await task is False
    else:
        with pytest.raises(LostLease):
            await task
    assert (await queue.list_jobs(claim.run_id))[0].status == "RUNNING"


async def test_http_backpressure_and_bounded_admission_wait(db, pg_url):
    provider, dataset, queue = await scenario(db)
    app = create_app(provider, database_url=pg_url, queue_capacity=1)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = {"dataset_id": str(dataset.id)}
            async with db.sessions.begin() as blocker:
                await blocker.execute(text("SELECT pg_advisory_xact_lock(8173,1)"))
                busy = await client.post(
                    "/queued-runs", json=data, headers={"Idempotency-Key": "busy"}
                )
                assert busy.status_code == 503 and busy.headers["retry-after"] == "1"
            first = await client.post(
                "/queued-runs", json=data, headers={"Idempotency-Key": "first"}
            )
            assert first.status_code == 202
            duplicate = await client.post(
                "/queued-runs", json=data, headers={"Idempotency-Key": "first"}
            )
            assert duplicate.json()["id"] == first.json()["id"]
            full = await client.post(
                "/queued-runs", json=data, headers={"Idempotency-Key": "second"}
            )
            assert full.status_code == 429 and full.headers["retry-after"] == "5"
            assert len(await queue.list_jobs(UUID(first.json()["id"]))) == 1


async def test_benchmark_preparation_failure_cancels_only_its_work(db, tmp_path, monkeypatch):
    """Failed admission must not leave persistent benchmark jobs stranded."""
    from types import SimpleNamespace

    from agenteval.platform_benchmark import variant

    provider, dataset, queue = await scenario(db)
    other = await queue.submit(RunCreate(dataset_id=dataset.id), provider, provider.model)
    original = JobQueue.submit
    calls = 0

    async def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected admission failure")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(JobQueue, "submit", fail_second)
    args = SimpleNamespace(
        output=str(tmp_path / "report.json"),
        jobs=21,
        seed=42,
        latency=0.005,
        failure_every=97,
        postgres_container=None,
    )
    with pytest.raises(RuntimeError, match="injected admission failure"):
        await variant(db, args, 1, 1, "throughput")
    async with db.sessions() as session:
        states = (await session.execute(select(Run.id, Run.status))).all()
    assert dict(states)[other] == "RUNNING"
    assert all(status == "CANCELED" for run_id, status in states if run_id != other)
