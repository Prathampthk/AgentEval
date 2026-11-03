"""Durable PostgreSQL jobs: short claims, fenced writes, persisted retry state."""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update

from agenteval.database import Database, MissingRecord
from agenteval.domain import EvaluationRequest, EvaluationResult
from agenteval.models import Dataset, Job, Result, Run, TestCase
from agenteval.persistence_schemas import JobView, RunCreate
from agenteval.providers import Provider


class SubmissionConflict(Exception):
    pass


class QueueFull(Exception):
    pass


class LostLease(Exception):
    pass


@dataclass(frozen=True)
class Claim:
    id: UUID
    run_id: UUID
    test_case_id: UUID
    dataset_id: UUID
    owner: str
    token: UUID
    attempt: int
    request: EvaluationRequest
    provider_timeout: float
    job_timeout: float


class JobQueue:
    def __init__(self, database: Database):
        self.db = database

    async def submit(
        self,
        data: RunCreate,
        provider: Provider,
        key: str,
        *,
        capacity: int = 1000,
        max_attempts: int = 3,
        provider_timeout: float = 30,
        job_timeout: float = 45,
    ) -> UUID:
        if not 1 <= len(key) <= 200 or not key.strip():
            raise ValueError("Idempotency key must contain 1–200 characters")
        if not 1 <= max_attempts <= 10 or capacity < 1:
            raise ValueError("Invalid queue policy")
        if not all(math.isfinite(t) and t > 0 for t in (provider_timeout, job_timeout)):
            raise ValueError("Timeouts must be positive and finite")
        config = {
            "prompt": data.prompt,
            "provider_timeout_seconds": provider_timeout,
            "job_timeout_seconds": job_timeout,
            "max_attempts": max_attempts,
            "temperature": 0 if not provider.simulated else None,
            "generation_max_output_tokens": 1024 if not provider.simulated else None,
            "judge_max_output_tokens": 2048 if not provider.simulated else None,
        }
        canonical = {
            "dataset_id": str(data.dataset_id),
            "configuration": config,
            "provider": provider.name,
            "model": provider.model,
            "simulated": provider.simulated,
            "rubric_version": "v1",
        }
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        async with self.db.sessions.begin() as session:
            # All admissions use this installation-wide lock. Concurrent draining can
            # only make the count conservative; it cannot cause over-admission.
            await session.execute(text("SELECT pg_advisory_xact_lock(8173, 1)"))
            existing = await session.scalar(select(Run).where(Run.submission_key == key))
            if existing:
                if existing.request_hash != digest:
                    raise SubmissionConflict
                return existing.id
            if await session.get(Dataset, data.dataset_id) is None:
                raise MissingRecord
            cases = (
                await session.scalars(
                    select(TestCase.id).where(TestCase.dataset_id == data.dataset_id)
                )
            ).all()
            active = await session.scalar(
                select(func.count()).select_from(Job).where(Job.status.in_(("PENDING", "RUNNING")))
            )
            if active + len(cases) > capacity:
                raise QueueFull
            run = Run(
                dataset_id=data.dataset_id,
                provider=provider.name,
                model=provider.model,
                simulated=provider.simulated,
                configuration=config,
                execution_mode="queued",
                submission_key=key,
                request_hash=digest,
            )
            session.add(run)
            await session.flush()
            session.add_all(
                Job(
                    run_id=run.id,
                    dataset_id=data.dataset_id,
                    test_case_id=case_id,
                    max_attempts=max_attempts,
                )
                for case_id in cases
            )
            return run.id

    async def claim(
        self, owner: str, provider: Provider, lease_seconds: float = 60
    ) -> Claim | None:
        self._duration(lease_seconds)
        if not 1 <= len(owner) <= 100:
            raise ValueError("Invalid worker ID")
        async with self.db.sessions.begin() as session:
            job = await session.scalar(
                select(Job)
                .join(Run, Run.id == Job.run_id)
                .where(
                    Job.status == "PENDING",
                    Job.available_at <= func.clock_timestamp(),
                    Run.provider == provider.name,
                    Run.model == provider.model,
                    Run.simulated == provider.simulated,
                )
                .order_by(Job.available_at, Job.id)
                .with_for_update(skip_locked=True, of=Job)
                .limit(1)
            )
            if job is None:
                return None
            run = await session.get(Run, job.run_id)
            case = await session.get(TestCase, job.test_case_id)
            dataset = await session.get(Dataset, job.dataset_id)
            job.status = "RUNNING"
            job.attempts += 1
            job.lease_owner = owner
            job.lease_token = uuid4()
            job.lease_expires_at = func.clock_timestamp() + timedelta(seconds=lease_seconds)
            job.started_at = func.clock_timestamp()
            return Claim(
                job.id,
                job.run_id,
                job.test_case_id,
                job.dataset_id,
                owner,
                job.lease_token,
                job.attempts,
                EvaluationRequest(
                    dataset_name=dataset.name,
                    dataset_version=dataset.version,
                    test_case_id=case.external_id,
                    question=case.question,
                    expected_answer=case.expected_answer,
                    context=case.context,
                    exact_match=case.exact_match,
                    prompt=run.configuration["prompt"],
                ),
                run.configuration["provider_timeout_seconds"],
                run.configuration["job_timeout_seconds"],
            )

    @staticmethod
    def _duration(value):
        if not math.isfinite(value) or not 0 < value <= 3600:
            raise ValueError("Duration must be finite and between 0 and 3600 seconds")

    @staticmethod
    def _owned(claim):
        return (
            Job.id == claim.id,
            Job.status == "RUNNING",
            Job.lease_owner == claim.owner,
            Job.lease_token == claim.token,
            Job.lease_expires_at > func.clock_timestamp(),
        )

    async def renew(self, claim: Claim, lease_seconds: float = 60) -> bool:
        self._duration(lease_seconds)
        async with self.db.sessions.begin() as session:
            result = await session.execute(
                update(Job)
                .where(*self._owned(claim))
                .values(lease_expires_at=func.clock_timestamp() + timedelta(seconds=lease_seconds))
            )
            return result.rowcount == 1

    async def _run_lock(self, session, run_id):
        run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run is None:
            raise MissingRecord
        return run

    async def _summarize(self, session, run):
        counts = dict(
            (
                await session.execute(
                    select(Job.status, func.count())
                    .where(Job.run_id == run.id)
                    .group_by(Job.status)
                )
            ).all()
        )
        if counts.get("PENDING", 0) or counts.get("RUNNING", 0):
            return
        run.completed_at = func.clock_timestamp()
        if counts.get("FAILED", 0):
            run.status, run.error_category = "FAILED", "job_failure"
        elif counts.get("CANCELED", 0):
            run.status, run.error_category = "CANCELED", "canceled"
        else:
            run.status, run.error_category = "COMPLETED", None

    async def complete(self, claim: Claim, result: EvaluationResult):
        async with self.db.sessions.begin() as session:
            run = await self._run_lock(session, claim.run_id)
            if (
                result.provider,
                result.model,
                result.rubric_version,
                result.simulated,
                result.test_case_id,
            ) != (
                run.provider,
                run.model,
                run.rubric_version,
                run.simulated,
                claim.request.test_case_id,
            ):
                raise ValueError("Result does not match claim configuration")
            updated = await session.execute(
                update(Job)
                .where(*self._owned(claim))
                .values(
                    status="COMPLETED",
                    completed_at=func.clock_timestamp(),
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                    last_error=None,
                )
            )
            if updated.rowcount != 1:
                raise LostLease
            session.add(
                Result(
                    job_id=claim.id,
                    run_id=claim.run_id,
                    dataset_id=claim.dataset_id,
                    test_case_id=claim.test_case_id,
                    answer=result.answer,
                    correctness=result.judgment.correctness,
                    relevance=result.judgment.relevance,
                    groundedness=result.judgment.groundedness,
                    explanation=result.judgment.explanation,
                    exact_match=result.exact_match,
                    passed=result.passed,
                    generation_latency_ms=result.generation_latency_ms,
                    judge_latency_ms=result.judge_latency_ms,
                    generation_input_tokens=result.generation_usage.input_tokens,
                    generation_output_tokens=result.generation_usage.output_tokens,
                    judge_input_tokens=result.judge_usage.input_tokens,
                    judge_output_tokens=result.judge_usage.output_tokens,
                )
            )
            await session.flush()
            await self._summarize(session, run)

    async def fail(self, claim: Claim, category: str, *, retryable: bool, delay_seconds: float = 0):
        if not 0 <= delay_seconds <= 3600 or not math.isfinite(delay_seconds):
            raise ValueError("Invalid retry delay")
        if not category or len(category) > 100:
            raise ValueError("Invalid failure category")
        async with self.db.sessions.begin() as session:
            run = await self._run_lock(session, claim.run_id)
            job = await session.scalar(select(Job).where(*self._owned(claim)).with_for_update())
            if job is None:
                raise LostLease
            retry = retryable and job.attempts < job.max_attempts
            job.status = "PENDING" if retry else "FAILED"
            job.last_error = category
            job.completed_at = None if retry else func.clock_timestamp()
            job.available_at = func.clock_timestamp() + timedelta(seconds=delay_seconds)
            job.lease_owner = job.lease_token = job.lease_expires_at = None
            await session.flush()
            await self._summarize(session, run)

    async def recover(self, limit: int = 100) -> int:
        async with self.db.sessions() as session:
            expired = (
                await session.execute(
                    select(Job.id, Job.run_id)
                    .where(Job.status == "RUNNING", Job.lease_expires_at <= func.clock_timestamp())
                    .order_by(Job.lease_expires_at)
                    .limit(limit)
                )
            ).all()
        count = 0
        for job_id, run_id in expired:
            async with self.db.sessions.begin() as session:
                run = await self._run_lock(session, run_id)
                job = await session.scalar(
                    select(Job)
                    .where(
                        Job.id == job_id,
                        Job.status == "RUNNING",
                        Job.lease_expires_at <= func.clock_timestamp(),
                    )
                    .with_for_update()
                )
                if job is None:
                    continue
                job.status = "PENDING" if job.attempts < job.max_attempts else "FAILED"
                job.completed_at = None if job.status == "PENDING" else func.clock_timestamp()
                job.available_at = func.clock_timestamp()
                job.last_error = "lease_expired"
                job.lease_owner = job.lease_token = job.lease_expires_at = None
                await session.flush()
                await self._summarize(session, run)
                count += 1
        return count

    async def cancel(self, run_id: UUID):
        async with self.db.sessions.begin() as session:
            run = await self._run_lock(session, run_id)
            if run.execution_mode != "queued":
                raise SubmissionConflict
            if run.status != "RUNNING":
                return
            await session.execute(
                update(Job)
                .where(Job.run_id == run_id, Job.status.in_(("PENDING", "RUNNING")))
                .values(
                    status="CANCELED",
                    completed_at=func.clock_timestamp(),
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                    last_error="canceled",
                )
            )
            await self._summarize(session, run)

    async def list_jobs(self, run_id: UUID) -> list[JobView]:
        async with self.db.sessions() as session:
            if await session.get(Run, run_id) is None:
                raise MissingRecord
            jobs = (
                await session.scalars(
                    select(Job).where(Job.run_id == run_id).order_by(Job.created_at, Job.id)
                )
            ).all()
            return [
                JobView(**{name: getattr(job, name) for name in JobView.model_fields})
                for job in jobs
            ]
