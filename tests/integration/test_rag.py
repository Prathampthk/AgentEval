import pytest
from sqlalchemy import func, select

from agenteval.models import Document, DocumentChunk
from agenteval.providers import FakeProvider, ProviderError
from agenteval.rag import DocumentCreate, RagEvaluation, answer, ingest, retrieve

pytestmark = pytest.mark.integration


async def test_pgvector_ingestion_retrieval_and_evaluation(db):
    provider = FakeProvider()
    first = await ingest(
        db, provider, DocumentCreate(title="France", content="Paris is the capital of France.")
    )
    await ingest(
        db,
        provider,
        DocumentCreate(
            title="Databases", content="PostgreSQL supports transactions and foreign keys."
        ),
    )
    assert (
        await ingest(
            db, provider, DocumentCreate(title="France", content="Paris is the capital of France.")
        )
        == first
    )
    rows = await retrieve(db, provider, "What is the capital of France?", 1)
    assert rows[0]["document_id"] == first["id"] and rows[0]["distance"] >= 0
    result = await answer(
        db,
        provider,
        RagEvaluation(
            question="What is the capital of France?",
            k=1,
            expected_answer="Paris",
            expected_document_ids=[first["id"]],
        ),
        scored=True,
    )
    assert result["recall_at_k"] == result["hit_rate_at_k"] == 1
    assert result["result"]["simulated"] and result["result"]["passed"]
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Document)) == 2
        assert await session.scalar(select(func.count()).select_from(DocumentChunk)) == 2


async def test_failed_embedding_leaves_no_partial_document(db):
    class Invalid(FakeProvider):
        async def embed(self, text):
            return [0] * 768

    with pytest.raises(ProviderError, match="invalid_embedding"):
        await ingest(db, Invalid(), DocumentCreate(title="bad", content="text"))
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Document)) == 0


async def test_embedding_configurations_do_not_mix(db):
    provider = FakeProvider()
    await ingest(db, provider, DocumentCreate(title="one", content="Paris France"))
    other = FakeProvider()
    other.embedding_model = "incompatible"
    assert await retrieve(db, other, "Paris France", 1) == []


async def test_rag_http_target(db, pg_url):
    import httpx

    from agenteval.api import create_app

    app = create_app(FakeProvider(), database_url=pg_url)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.post("/rag/ask", json={"question": "France?"})).status_code == 422
            response = await client.post(
                "/documents", json={"title": "France", "content": "Paris is the capital of France."}
            )
            assert response.status_code == 201
            document = response.json()
            response = await client.post(
                "/rag/ask", json={"question": "What is the capital of France?", "k": 1}
            )
            assert response.status_code == 200 and "Paris" in response.json()["answer"]
            response = await client.post(
                "/rag/evaluate",
                json={
                    "question": "What is the capital of France?",
                    "k": 1,
                    "expected_answer": "Paris",
                    "expected_document_ids": [document["id"]],
                },
            )
            assert response.status_code == 200 and response.json()["recall_at_k"] == 1


async def test_large_retrieval_uses_same_bounded_evidence_for_ask_and_evaluate(db, pg_url):
    import httpx

    from agenteval.api import create_app
    from agenteval.domain import MAX_CONTEXT_CHARACTERS

    class Capture(FakeProvider):
        contexts = []

        async def generate(self, data):
            self.contexts.append(data.context)
            return await super().generate(data)

    provider = Capture()
    ids = []
    for i in range(3):
        result = await ingest(
            db,
            provider,
            DocumentCreate(title=f"large-{i}", content=("Paris" + "x" * 995 + " ") * 5),
        )
        ids.append(result["id"])
    app = create_app(provider, database_url=pg_url)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            ask = await client.post("/rag/ask", json={"question": "Paris?", "k": 3})
            scored = await client.post(
                "/rag/evaluate",
                json={
                    "question": "Paris?",
                    "k": 3,
                    "expected_answer": "Paris",
                    "expected_document_ids": ids,
                },
            )
    assert ask.status_code == scored.status_code == 200
    assert provider.contexts[0] == provider.contexts[1]
    for response in (ask, scored):
        data = response.json()
        assert data["context_truncated"] and data["context_characters"] <= MAX_CONTEXT_CHARACTERS
        assert data["context_chunk_ids"]
    assert scored.json()["recall_at_k"] == 1  # Ranked retrieval, distinct from context selection.


async def test_rag_generation_timeout_is_provider_504_for_both_paths(db, pg_url):
    import httpx

    from agenteval.api import create_app

    class Timeout(FakeProvider):
        async def generate(self, data):
            raise TimeoutError()

    provider = Timeout()
    document = await ingest(db, provider, DocumentCreate(title="France", content="Paris"))
    app = create_app(provider, database_url=pg_url)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path, body in [
                ("/rag/ask", {"question": "Paris?"}),
                (
                    "/rag/evaluate",
                    {
                        "question": "Paris?",
                        "expected_answer": "Paris",
                        "expected_document_ids": [document["id"]],
                    },
                ),
            ]:
                response = await client.post(path, json=body)
                assert response.status_code == 504
                assert response.json()["detail"] == {"category": "timeout", "retryable": True}
