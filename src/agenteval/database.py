"""Short-lived database sessions; never retain a connection during provider calls."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agenteval.domain import EvaluationResult, Judgment, Usage
from agenteval.models import Dataset, Result, Run, TestCase
from agenteval.persistence_schemas import DatasetCase, DatasetCreate, DatasetView, RunView


class MissingRecord(Exception):
    pass


class DatasetConflict(Exception):
    pass


class RunConflict(Exception):
    pass


class Database:
    def __init__(self, url: str):
        if make_url(url).drivername != "postgresql+asyncpg":
            raise ValueError("Database URL must use postgresql+asyncpg")
        self.engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=0,
            pool_timeout=5,
            hide_parameters=True,
            connect_args={
                "timeout": 5,
                "command_timeout": 10,
                "server_settings": {"statement_timeout": "10000"},
            },
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self):
        await self.engine.dispose()

    async def check_ready(self):
        async with self.sessions() as session:
            version = await session.scalar(text("SELECT version_num FROM alembic_version"))
            if version != "0001":
                raise RuntimeError("Database migrations are not current")

    async def create_dataset(self, data: DatasetCreate) -> tuple[DatasetView, bool]:
        # Stable ordering makes equivalent content independent of request order.
        cases = sorted(data.cases, key=lambda case: case.external_id)
        canonical = json.dumps(
            [c.model_dump() for c in cases], sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        async with self.sessions.begin() as session:
            dataset_id = await session.scalar(
                insert(Dataset)
                .values(name=data.name, version=data.version, content_hash=digest)
                .on_conflict_do_nothing(constraint="uq_dataset_version")
                .returning(Dataset.id)
            )
            created = dataset_id is not None
            if not created:
                existing = await session.scalar(
                    select(Dataset).where(
                        Dataset.name == data.name, Dataset.version == data.version
                    )
                )
                if existing.content_hash != digest:
                    raise DatasetConflict
                dataset_id = existing.id
            else:
                session.add_all(
                    TestCase(dataset_id=dataset_id, **case.model_dump()) for case in cases
                )
        return await self.get_dataset(dataset_id), created

    async def get_dataset(self, dataset_id: UUID) -> DatasetView:
        async with self.sessions() as session:
            dataset = await session.get(Dataset, dataset_id)
            if dataset is None:
                raise MissingRecord
            cases = (
                await session.scalars(
                    select(TestCase)
                    .where(TestCase.dataset_id == dataset_id)
                    .order_by(TestCase.external_id)
                )
            ).all()
            return DatasetView(
                id=dataset.id,
                name=dataset.name,
                version=dataset.version,
                content_hash=dataset.content_hash,
                created_at=dataset.created_at,
                cases=[
                    DatasetCase(
                        external_id=c.external_id,
                        question=c.question,
                        expected_answer=c.expected_answer,
                        context=c.context,
                        exact_match=c.exact_match,
                    )
                    for c in cases
                ],
            )

    async def start_run(self, dataset_id: UUID, provider, configuration: dict) -> UUID:
        async with self.sessions.begin() as session:
            if await session.get(Dataset, dataset_id) is None:
                raise MissingRecord
            run = Run(
                dataset_id=dataset_id,
                provider=provider.name,
                model=provider.model,
                simulated=provider.simulated,
                configuration=configuration,
            )
            session.add(run)
            await session.flush()
            return run.id

    async def finish_run(self, run_id: UUID, results: list[EvaluationResult]):
        async with self.sessions.begin() as session:
            # Terminal state and all results commit together or roll back together.
            run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if run is None:
                raise MissingRecord
            if run.status != "RUNNING":
                raise RunConflict
            cases = (
                await session.scalars(select(TestCase).where(TestCase.dataset_id == run.dataset_id))
            ).all()
            ids = {case.external_id: case.id for case in cases}
            if len(results) != len(ids) or {r.test_case_id for r in results} != set(ids):
                raise ValueError("A completed run requires exactly one result per dataset case")
            for result in results:
                if (result.provider, result.model, result.rubric_version, result.simulated) != (
                    run.provider,
                    run.model,
                    run.rubric_version,
                    run.simulated,
                ):
                    raise ValueError("Result configuration does not match the run snapshot")
                session.add(
                    Result(
                        run_id=run.id,
                        dataset_id=run.dataset_id,
                        test_case_id=ids[result.test_case_id],
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
            run.status = "COMPLETED"
            run.completed_at = text("CURRENT_TIMESTAMP")

    async def fail_run(self, run_id: UUID, category: str):
        async with self.sessions.begin() as session:
            await session.execute(
                update(Run)
                .where(Run.id == run_id, Run.status == "RUNNING")
                .values(
                    status="FAILED", error_category=category, completed_at=text("CURRENT_TIMESTAMP")
                )
            )

    async def get_run(self, run_id: UUID) -> RunView:
        async with self.sessions.begin() as session:
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            run = await session.get(Run, run_id)
            if run is None:
                raise MissingRecord
            dataset = await session.get(Dataset, run.dataset_id)
            rows = (
                await session.execute(
                    select(Result, TestCase.external_id)
                    .join(TestCase, Result.test_case_id == TestCase.id)
                    .where(Result.run_id == run.id)
                    .order_by(TestCase.external_id)
                )
            ).all()
            return RunView(
                id=run.id,
                dataset_id=run.dataset_id,
                status=run.status,
                provider=run.provider,
                model=run.model,
                rubric_version=run.rubric_version,
                simulated=run.simulated,
                configuration=run.configuration,
                created_at=run.created_at,
                completed_at=run.completed_at,
                error_category=run.error_category,
                results=[
                    EvaluationResult(
                        dataset_name=dataset.name,
                        dataset_version=dataset.version,
                        test_case_id=external_id,
                        provider=run.provider,
                        model=run.model,
                        rubric_version=run.rubric_version,
                        simulated=run.simulated,
                        answer=r.answer,
                        judgment=Judgment(
                            correctness=r.correctness,
                            relevance=r.relevance,
                            groundedness=r.groundedness,
                            explanation=r.explanation,
                        ),
                        exact_match=r.exact_match,
                        passed=r.passed,
                        generation_latency_ms=r.generation_latency_ms,
                        judge_latency_ms=r.judge_latency_ms,
                        generation_usage=Usage(
                            input_tokens=r.generation_input_tokens,
                            output_tokens=r.generation_output_tokens,
                        ),
                        judge_usage=Usage(
                            input_tokens=r.judge_input_tokens, output_tokens=r.judge_output_tokens
                        ),
                    )
                    for r, external_id in rows
                ],
            )

    async def list_runs(self, dataset_id: UUID, limit: int) -> list[RunView]:
        async with self.sessions() as session:
            ids = (
                await session.scalars(
                    select(Run.id)
                    .where(Run.dataset_id == dataset_id)
                    .order_by(Run.created_at.desc(), Run.id)
                    .limit(limit)
                )
            ).all()
        return [await self.get_run(run_id) for run_id in ids]
