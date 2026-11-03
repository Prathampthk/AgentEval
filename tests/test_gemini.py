from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from google.genai import errors, types

from agenteval.domain import GenerationInput, JudgeInput
from agenteval.gemini import GeminiProvider
from agenteval.providers import ProviderError


def adapter(response=None, error=None):
    call = AsyncMock(return_value=response, side_effect=error)
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=call)))
    return GeminiProvider(client, "test-model"), call


async def test_generate_contract_and_missing_usage():
    provider, call = adapter(
        types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(parts=[types.Part(text="Paris")]))]
        )
    )
    result = await provider.generate(
        GenerationInput(question="Capital?", context="Paris", prompt="Answer")
    )
    assert result.text == "Paris"
    assert result.usage.input_tokens is None
    assert call.await_args.kwargs["model"] == "test-model"
    assert "expected_answer" not in call.await_args.kwargs["contents"]


async def test_structured_judgment_contract():
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    parts=[
                        types.Part(
                            text='{"correctness":2,"relevance":2,"groundedness":2,"explanation":"supported"}'
                        )
                    ]
                )
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=12, candidates_token_count=8
        ),
    )
    provider, call = adapter(response)
    result = await provider.judge(
        JudgeInput(question="Capital?", expected_answer="Paris", context="Paris", answer="Paris")
    )
    assert result.judgment.correctness == 2
    assert result.usage.input_tokens == 12
    assert call.await_args.kwargs["config"].response_mime_type == "application/json"


@pytest.mark.parametrize("text", ["not json", '{"correctness":99}', "{}"])
async def test_malformed_judge_output(text):
    provider, _ = adapter(
        types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(parts=[types.Part(text=text)]))]
        )
    )
    with pytest.raises(ProviderError, match="invalid_output"):
        await provider.judge(JudgeInput(question="q", expected_answer="a", context="", answer="a"))


@pytest.mark.parametrize(
    "code,category,retryable",
    [
        (400, "invalid_request", False),
        (401, "authentication", False),
        (403, "authorization", False),
        (404, "model_not_found", False),
        (429, "rate_limit", True),
        (503, "unavailable", True),
    ],
)
async def test_api_error_classification(code, category, retryable):
    provider, _ = adapter(error=errors.APIError(code, {"message": "sensitive text"}))
    with pytest.raises(ProviderError) as caught:
        await provider.generate(GenerationInput(question="q", context="", prompt="p"))
    assert caught.value.category == category
    assert caught.value.retryable == retryable
    assert "sensitive" not in str(caught.value)


async def test_transport_timeout():
    provider, _ = adapter(error=httpx.ReadTimeout("sensitive URL"))
    with pytest.raises(ProviderError, match="timeout"):
        await provider.generate(GenerationInput(question="q", context="", prompt="p"))


async def test_missing_generated_text_is_invalid_output():
    provider, _ = adapter(types.GenerateContentResponse())
    with pytest.raises(ProviderError, match="invalid_output"):
        await provider.generate(GenerationInput(question="q", context="", prompt="p"))


async def test_embedding_sdk_contract():
    call = AsyncMock(
        return_value=types.EmbedContentResponse(
            embeddings=[types.ContentEmbedding(values=[1.0] * 768)]
        )
    )
    provider = GeminiProvider(
        SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=call))),
        "test-model",
    )
    vector = await provider.embed("hello")
    assert len(vector) == 768
    assert call.await_args.kwargs["config"].output_dimensionality == 768


async def test_invalid_embedding_response_rejected():
    call = AsyncMock(return_value=types.EmbedContentResponse(embeddings=[]))
    provider = GeminiProvider(
        SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=call))),
        "test-model",
    )
    with pytest.raises(ProviderError, match="invalid_embedding"):
        await provider.embed("hello")


def test_retry_after_guidance_is_parsed_safely():
    from agenteval.gemini import retry_after

    assert retry_after("12") == 12
    assert retry_after("nan") is None
    assert retry_after("invalid") is None
    assert retry_after("Wed, 01 Jan 2020 00:00:00 GMT") == 0


async def test_retry_after_header_preserved_without_error_content():
    response = httpx.Response(429, headers={"retry-after": "3"})
    provider, _ = adapter(error=errors.APIError(429, {"message": "secret content"}, response))
    with pytest.raises(ProviderError) as caught:
        await provider.generate(GenerationInput(question="q", context="", prompt="p"))
    assert caught.value.retry_after_seconds == 3 and "secret" not in str(caught.value)


async def test_connection_and_pool_timeout_are_separate_from_read_timeout():
    from agenteval.runtime import connection_timeout_bounds

    observed = {}

    def handler(request):
        observed.update(request.extensions["timeout"])
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), event_hooks={"request": [connection_timeout_bounds]}
    ) as client:
        await client.get("https://example.test", timeout=30)
    assert observed == dict(connect=5, read=30, write=30, pool=5)
