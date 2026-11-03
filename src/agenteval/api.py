"""Local demonstration API; with optional PostgreSQL persistence; no public authentication."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from agenteval.database import Database, DatasetConflict, MissingRecord
from agenteval.domain import EvaluationRequest, EvaluationResult
from agenteval.jobs import JobQueue, QueueFull, SubmissionConflict
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
from agenteval.runtime import provider_context
from agenteval.service import evaluate

logger = logging.getLogger("agenteval")


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
    provider: Provider | None = None, timeout_seconds: float = 30, database_url: str | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        async with provider_context(provider, timeout_seconds) as selected:
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
            raise HTTPException(429, "Evaluation capacity reached") from None
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
                504 if exc.category == "timeout" else 502,
                {"category": exc.category, "retryable": exc.retryable},
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
            )
        except SubmissionConflict:
            raise HTTPException(
                409, "Idempotency-Key conflicts with an earlier submission"
            ) from None
        except QueueFull:
            raise HTTPException(429, "Persistent job queue capacity reached") from None
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
            status_code=504 if exc.category == "timeout" else 502,
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

    return app


app = create_app()
