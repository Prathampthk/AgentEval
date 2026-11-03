"""Request-scoped evaluation orchestration, independent of FastAPI."""

import asyncio
from time import perf_counter

from pydantic import ValidationError

from agenteval.domain import EvaluationRequest, EvaluationResult, GenerationInput, JudgeInput
from agenteval.providers import Provider, ProviderError


async def evaluate(
    data: EvaluationRequest, provider: Provider, timeout_seconds: float = 30
) -> EvaluationResult:
    try:
        start = perf_counter()
        async with asyncio.timeout(timeout_seconds):
            generation = await provider.generate(
                GenerationInput(question=data.question, context=data.context, prompt=data.prompt)
            )
        generation_ms = (perf_counter() - start) * 1000
        start = perf_counter()
        async with asyncio.timeout(timeout_seconds):
            judged = await provider.judge(
                JudgeInput(
                    question=data.question,
                    expected_answer=data.expected_answer,
                    context=data.context,
                    answer=generation.text,
                )
            )
        judge_ms = (perf_counter() - start) * 1000
        if bool(data.context) != (judged.judgment.groundedness is not None):
            raise ProviderError("invalid_output")
    except TimeoutError:
        raise ProviderError("timeout", retryable=True) from None
    except ValidationError:
        raise ProviderError("invalid_output") from None

    exact = generation.text.strip() == data.expected_answer.strip() if data.exact_match else None
    scores = judged.judgment
    passed = (
        scores.correctness == 2
        and scores.relevance == 2
        and (not data.context or scores.groundedness == 2)
        and exact is not False
    )
    return EvaluationResult(
        dataset_name=data.dataset_name,
        dataset_version=data.dataset_version,
        test_case_id=data.test_case_id,
        provider=provider.name,
        model=provider.model,
        answer=generation.text,
        judgment=scores,
        exact_match=exact,
        passed=passed,
        generation_latency_ms=generation_ms,
        judge_latency_ms=judge_ms,
        generation_usage=generation.usage,
        judge_usage=judged.usage,
        simulated=provider.simulated,
    )
