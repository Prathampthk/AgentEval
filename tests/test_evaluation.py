import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agenteval.api import create_app
from agenteval.domain import EvaluationRequest, JudgeResponse, Judgment, TextResponse
from agenteval.providers import FakeProvider, ProviderError
from agenteval.service import evaluate

PAYLOAD = dict(
    dataset_name="geography",
    dataset_version="1",
    test_case_id="capital",
    question="What is the capital of France?",
    expected_answer="Paris",
    context="Paris",
    exact_match=True,
)


def test_http_evaluation_and_health():
    with TestClient(create_app(FakeProvider())) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/health/ready").json()["remote_access_verified"] is False
        response = client.post("/evaluations", json=PAYLOAD)
        assert response.status_code == 200
        result = response.json()
        assert result["passed"] and result["simulated"] and result["exact_match"]
        assert result["generation_usage"]["input_tokens"] is None
        assert result["generation_latency_ms"] >= 0


def test_low_quality_is_a_result_not_provider_failure():
    with TestClient(create_app(FakeProvider())) as client:
        response = client.post("/evaluations", json={**PAYLOAD, "expected_answer": "London"})
        assert response.status_code == 200
        assert response.json()["passed"] is False


@pytest.mark.parametrize("change", [{"question": " "}, {"unknown": 1}, {"context": "x" * 12001}])
def test_input_validation(change):
    with TestClient(create_app(FakeProvider())) as client:
        assert client.post("/evaluations", json={**PAYLOAD, **change}).status_code == 422


def test_body_limit():
    with TestClient(create_app(FakeProvider())) as client:
        assert client.post("/evaluations", content=b"x" * 32769).status_code == 413


async def test_answer_key_not_sent_to_generation():
    class Spy(FakeProvider):
        async def generate(self, data):
            assert set(data.model_dump()) == {"question", "context", "prompt"}
            assert "secret-answer" not in data.model_dump_json()
            return TextResponse(text="response")

    result = await evaluate(
        EvaluationRequest(**{**PAYLOAD, "expected_answer": "secret-answer"}), Spy()
    )
    assert result.passed is False


async def test_no_context_uses_null_groundedness():
    result = await evaluate(EvaluationRequest(**{**PAYLOAD, "context": ""}), FakeProvider())
    assert result.judgment.groundedness is None


@pytest.mark.parametrize("value", [-1, 3, True, "2"])
def test_invalid_scores_rejected(value):
    with pytest.raises(ValidationError):
        Judgment(correctness=value, relevance=2, explanation="test")


async def test_context_requires_groundedness():
    class Invalid(FakeProvider):
        async def judge(self, data):
            return JudgeResponse(judgment=Judgment(correctness=2, relevance=2, explanation="bad"))

    with pytest.raises(ProviderError, match="invalid_output"):
        await evaluate(EvaluationRequest(**PAYLOAD), Invalid())


def test_provider_error_redacted():
    class Failed(FakeProvider):
        async def generate(self, data):
            raise ProviderError("authentication")

    with TestClient(create_app(Failed())) as client:
        response = client.post("/evaluations", json=PAYLOAD)
        assert response.status_code == 502
        assert response.json()["detail"] == {"category": "authentication", "retryable": False}


async def test_timeout_cancels_provider():
    canceled = asyncio.Event()

    class Slow(FakeProvider):
        async def generate(self, data):
            try:
                await asyncio.Event().wait()
            finally:
                canceled.set()

    with pytest.raises(ProviderError, match="timeout"):
        await evaluate(EvaluationRequest(**PAYLOAD), Slow(), timeout_seconds=0.01)
    assert canceled.is_set()


async def test_caller_cancellation_propagates():
    class Slow(FakeProvider):
        async def generate(self, data):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await evaluate(EvaluationRequest(**PAYLOAD), Slow())


async def test_capacity_rejects_excess_and_releases_slots():
    import httpx

    started = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum = 0

    class Blocking(FakeProvider):
        async def generate(self, data):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 4:
                started.set()
            try:
                await release.wait()
                return await super().generate(data)
            finally:
                active -= 1

    app = create_app(Blocking())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            tasks = [
                asyncio.create_task(client.post("/evaluations", json=PAYLOAD)) for _ in range(4)
            ]
            try:
                await asyncio.wait_for(started.wait(), 2)
                assert (await client.post("/evaluations", json=PAYLOAD)).status_code == 429
            finally:
                release.set()
                responses = await asyncio.gather(*tasks)
            assert all(response.status_code == 200 for response in responses)
            assert maximum == 4
            assert app.state.slots.qsize() == 4
            assert (await client.post("/evaluations", json=PAYLOAD)).status_code == 200


async def test_canceled_api_request_releases_slot():
    import httpx

    started = asyncio.Event()

    class Blocking(FakeProvider):
        async def generate(self, data):
            started.set()
            await asyncio.Event().wait()

    app = create_app(Blocking())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            task = asyncio.create_task(client.post("/evaluations", json=PAYLOAD))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert app.state.slots.qsize() == 4


def test_failure_releases_api_slot():
    class Failed(FakeProvider):
        async def generate(self, data):
            raise ProviderError("unavailable", True)

    app = create_app(Failed())
    with TestClient(app) as client:
        for _ in range(5):
            assert client.post("/evaluations", json=PAYLOAD).status_code == 502
        assert app.state.slots.qsize() == 4


def test_api_timeout_returns_504_and_releases_capacity():
    class Slow(FakeProvider):
        async def generate(self, data):
            await asyncio.Event().wait()

    app = create_app(Slow(), timeout_seconds=0.01)
    with TestClient(app) as client:
        response = client.post("/evaluations", json=PAYLOAD)
        assert response.status_code == 504
        assert response.json()["detail"]["category"] == "timeout"
        assert app.state.slots.qsize() == 4


def test_gemini_mode_requires_configuration(monkeypatch):
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AGENTEVAL_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="requires GEMINI_API_KEY"):
        with TestClient(create_app()):
            pass


async def test_judge_timeout():
    class SlowJudge(FakeProvider):
        async def judge(self, data):
            await asyncio.Event().wait()

    with pytest.raises(ProviderError, match="timeout"):
        await evaluate(EvaluationRequest(**PAYLOAD), SlowJudge(), timeout_seconds=0.01)
