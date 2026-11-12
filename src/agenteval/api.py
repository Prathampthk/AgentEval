"""Local demonstration API with persistence and optional single-owner access control."""

import asyncio
import json
import logging
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from agenteval.access import OwnerAccess, validate_access_token
from agenteval.database import Database, DatasetConflict, MissingRecord
from agenteval.domain import EvaluationRequest, EvaluationResult, StrictModel
from agenteval.jobs import JobQueue, QueueBusy, QueueFull, SubmissionConflict
from agenteval.models import Dataset, Job, Result, Run, TestCase
from agenteval.persistence_schemas import (
    DatasetCreate,
    DatasetView,
    JobView,
    QueuedRunCreate,
    RunCreate,
    RunView,
)
from agenteval.persistent_runs import execute_run
from agenteval.providers import Provider, ProviderError
from agenteval.rag import DocumentCreate, RagEvaluation, RagQuestion, answer, ingest
from agenteval.regression import RegressionPolicy, compare, comparison_input
from agenteval.runtime import provider_context
from agenteval.service import evaluate

logger = logging.getLogger("agenteval")


def provider_http_status(exc):
    if exc.category in {"provider_budget_exhausted", "provider_rate_limited", "provider_capacity"}:
        return 429
    if exc.category == "provider_budget_unavailable":
        return 503
    return 504 if exc.category == "timeout" else 502


def provider_retry_headers(exc):
    return (
        {"Retry-After": str(max(1, math.ceil(exc.retry_after_seconds)))}
        if exc.retry_after_seconds is not None
        else {}
    )


class ComparisonRequest(StrictModel):
    baseline_run_id: UUID
    candidate_run_id: UUID
    policy: RegressionPolicy = RegressionPolicy()


class BodyLimit:
    def __init__(self, app, limit=32768):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                return await JSONResponse({"detail": "Request body too large"}, 413)(
                    scope, receive, send
                )
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(
    provider: Provider | None = None,
    timeout_seconds: float = 30,
    database_url: str | None = None,
    queue_capacity: int | None = None,
    access_token: str | None = None,
) -> FastAPI:
    token = access_token if access_token is not None else os.getenv("AGENTEVAL_ACCESS_TOKEN", "")
    validate_access_token(token)

    @asynccontextmanager
    async def lifespan(app):
        async with provider_context(provider, timeout_seconds) as selected:
            capacity = (
                queue_capacity
                if queue_capacity is not None
                else int(os.getenv("AGENTEVAL_QUEUE_CAPACITY", "1000"))
            )
            if type(capacity) is not int or not 1 <= capacity <= 100000:
                raise RuntimeError("AGENTEVAL_QUEUE_CAPACITY must be 1–100000")
            app.state.queue_capacity = capacity
            app.state.provider = selected
            url = database_url or os.getenv("AGENTEVAL_DATABASE_URL")
            app.state.database = Database(url) if url else None
            app.state.slots = asyncio.Queue(maxsize=4)
            for _ in range(4):
                app.state.slots.put_nowait(None)
            try:
                yield
            finally:
                if app.state.database:
                    await app.state.database.close()

    app = FastAPI(title="AgentEval", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyLimit)
    app.add_middleware(OwnerAccess, token=token)

    @app.exception_handler(OSError)
    @app.exception_handler(TimeoutError)
    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logger.warning('{"event":"database_failure"}')
        return JSONResponse({"detail": "Database unavailable or write rejected"}, status_code=503)

    @app.exception_handler(MissingRecord)
    async def missing_record(request, exc):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    def database():
        if app.state.database is None:
            raise HTTPException(503, "PostgreSQL persistence is not configured")
        return app.state.database

    @asynccontextmanager
    async def evaluation_slot():
        try:
            app.state.slots.get_nowait()
        except asyncio.QueueEmpty:
            raise HTTPException(
                429, "Evaluation capacity reached", headers={"Retry-After": "1"}
            ) from None
        try:
            yield
        finally:
            app.state.slots.put_nowait(None)

    @app.get("/health/live")
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        selected = app.state.provider
        if app.state.database:
            try:
                await app.state.database.check_ready()
            except (SQLAlchemyError, OSError, TimeoutError, RuntimeError):
                raise HTTPException(503, "Database unavailable or migrations not current") from None
        return {
            "status": "configured",
            "provider": selected.name,
            "model": selected.model,
            "embedding_model": getattr(selected, "embedding_model", None),
            "judge_prompt_version": getattr(selected, "judge_prompt_version", "v1"),
            "simulated": selected.simulated,
            "remote_access_verified": False,
            "database": "ready" if app.state.database else "disabled",
        }

    @app.post("/evaluations", response_model=EvaluationResult)
    async def submit(data: EvaluationRequest):
        async with evaluation_slot():
            return await evaluate_http(data)

    async def evaluate_http(data):
        try:
            result = await evaluate(data, app.state.provider, timeout_seconds)
            logger.info(
                '{"event":"evaluation_completed","simulated":%s,"passed":%s}',
                str(result.simulated).lower(),
                str(result.passed).lower(),
            )
            return result
        except ProviderError as exc:
            logger.warning('{"event":"provider_failure","category":"%s"}', exc.category)
            raise HTTPException(
                provider_http_status(exc),
                {"category": exc.category, "retryable": exc.retryable},
                headers=provider_retry_headers(exc),
            ) from None

    @app.post("/datasets", response_model=DatasetView, status_code=201)
    async def create_dataset(data: DatasetCreate, response: Response):
        try:
            dataset, created = await database().create_dataset(data)
        except DatasetConflict:
            raise HTTPException(
                409, "Dataset version already exists with different content"
            ) from None
        response.status_code = 201 if created else 200
        return dataset

    @app.get("/datasets/{dataset_id}", response_model=DatasetView)
    async def get_dataset(dataset_id: UUID):
        return await database().get_dataset(dataset_id)

    @app.post("/runs", response_model=RunView, status_code=201)
    async def create_run(data: RunCreate):
        db = database()
        async with evaluation_slot():
            return await execute_run(data, db, app.state.provider, timeout_seconds)

    @app.get("/runs/{run_id}", response_model=RunView)
    async def get_run(run_id: UUID):
        return await database().get_run(run_id)

    @app.get("/runs", response_model=list[RunView])
    async def list_runs(dataset_id: UUID, limit: int = 20):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "limit must be between 1 and 100")
        return await database().list_runs(dataset_id, limit)

    @app.post("/queued-runs", response_model=RunView, status_code=202)
    async def submit_queued_run(
        data: QueuedRunCreate, idempotency_key: str = Header(min_length=1, max_length=200)
    ):
        if not idempotency_key.strip():
            raise HTTPException(422, "Idempotency-Key must not be blank")
        db = database()
        try:
            run_id = await JobQueue(db).submit(
                data,
                app.state.provider,
                idempotency_key,
                provider_timeout=timeout_seconds,
                run_timeout=data.run_timeout_seconds,
                capacity=app.state.queue_capacity,
            )
        except SubmissionConflict:
            raise HTTPException(
                409, "Idempotency-Key conflicts with an earlier submission"
            ) from None
        except QueueFull:
            raise HTTPException(
                429, "Persistent job queue capacity reached", headers={"Retry-After": "5"}
            ) from None
        except QueueBusy:
            raise HTTPException(
                503,
                "Queue admission is busy; retry with the same Idempotency-Key",
                headers={"Retry-After": "1"},
            ) from None
        return await db.get_run(run_id)

    @app.get("/runs/{run_id}/jobs", response_model=list[JobView])
    async def get_jobs(run_id: UUID):
        return await JobQueue(database()).list_jobs(run_id)

    @app.post("/runs/{run_id}/cancel", response_model=RunView)
    async def cancel_run(run_id: UUID):
        db = database()
        try:
            await JobQueue(db).cancel(run_id)
        except SubmissionConflict:
            raise HTTPException(409, "Only queued runs support cancellation") from None
        return await db.get_run(run_id)

    @app.exception_handler(ProviderError)
    async def provider_failure(request, exc):
        return JSONResponse(
            {"detail": {"category": exc.category, "retryable": exc.retryable}},
            status_code=provider_http_status(exc),
            headers=provider_retry_headers(exc),
        )

    @app.post("/documents", status_code=201)
    async def ingest_document(data: DocumentCreate):
        try:
            async with evaluation_slot():
                return await ingest(database(), app.state.provider, data)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/rag/ask")
    async def rag_answer(data: RagQuestion):
        try:
            async with evaluation_slot():
                return await answer(database(), app.state.provider, data)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/rag/evaluate")
    async def rag_evaluate(data: RagEvaluation):
        try:
            async with evaluation_slot():
                return await answer(database(), app.state.provider, data, scored=True)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/runs/{run_id}/comparison-input")
    async def export_comparison(run_id: UUID):
        db = database()
        run = await db.get_run(run_id)
        dataset = await db.get_dataset(run.dataset_id)
        return comparison_input(run, len(dataset.cases))

    @app.post("/comparisons")
    async def compare_runs(data: ComparisonRequest):
        db = database()
        baseline = await db.get_run(data.baseline_run_id)
        candidate = await db.get_run(data.candidate_run_id)
        left = await db.get_dataset(baseline.dataset_id)
        right = await db.get_dataset(candidate.dataset_id)
        return compare(
            comparison_input(baseline, len(left.cases)),
            comparison_input(candidate, len(right.cases)),
            data.policy,
        )

    @app.get("/datasets")
    async def list_datasets():
        async with database().sessions() as session:
            rows = (
                await session.execute(
                    select(Dataset, func.count(TestCase.id))
                    .join(TestCase)
                    .group_by(Dataset.id)
                    .order_by(Dataset.created_at.desc())
                    .limit(50)
                )
            ).all()
            return [
                {"id": str(d.id), "name": d.name, "version": d.version, "case_count": count}
                for d, count in rows
            ]

    @app.get("/overview")
    async def overview():
        async with database().sessions() as session:
            runs = dict(
                (await session.execute(select(Run.status, func.count()).group_by(Run.status))).all()
            )
            jobs = dict(
                (await session.execute(select(Job.status, func.count()).group_by(Job.status))).all()
            )
            row = (
                await session.execute(
                    select(
                        func.count(Result.id),
                        func.count().filter(Result.passed),
                        func.avg(Result.correctness),
                        func.avg(Result.relevance),
                        func.avg(Result.groundedness),
                        func.avg(Result.generation_latency_ms + Result.judge_latency_ms),
                    )
                )
            ).one()
            simulated = await session.scalar(
                select(func.count()).select_from(Run).where(Run.simulated)
            )
            latest = (
                await session.execute(
                    select(Run.id, Run.status).order_by(Run.created_at.desc()).limit(1)
                )
            ).first()
            return {
                "simulated_runs": simulated,
                "latest_run": {"id": str(latest.id), "status": latest.status} if latest else None,
                "total_runs": sum(runs.values()),
                "runs": runs,
                "jobs": jobs,
                "result_count": row[0],
                "passed": row[1],
                "failed_quality": row[0] - row[1],
                "average_correctness": row[2],
                "average_relevance": row[3],
                "average_groundedness": row[4],
                "average_latency_ms": row[5],
            }

    @app.get("/judge-validation")
    async def judge_report():
        path = (
            Path(os.getenv("AGENTEVAL_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
            / "reports"
            / "judge_validation.json"
        )
        return (
            json.loads(path.read_text())
            if path.exists()
            else {"status": "BLOCKED", "paired_count": 0}
        )

    # Serve the built dashboard when present. Source-only API installations remain valid.
    from fastapi.staticfiles import StaticFiles

    dashboard = (
        Path(os.getenv("AGENTEVAL_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
        / "frontend"
        / "dist"
    )
    if dashboard.is_dir():
        app.mount("/dashboard", StaticFiles(directory=dashboard, html=True), name="dashboard")

    return app


app = create_app()
