import pytest

from agenteval.benchmark import SimulatedProvider, distribution
from agenteval.domain import GenerationInput
from agenteval.providers import ProviderError


def test_nearest_rank_quantiles():
    result = distribution(list(range(1, 1001)))
    assert result["p50"] == 500 and result["p95"] == 950 and result["p99"] == 990
    assert result["count"] == 1000 and distribution([]) is None


async def test_injected_failure_is_once_per_case_not_every_retry():
    provider = SimulatedProvider("unit", 0.0001, 97)
    data = GenerationInput(question="case 0", context="Paris", prompt="Answer")
    with pytest.raises(ProviderError, match="rate_limit"):
        await provider.generate(data)
    assert (await provider.generate(data)).text == "Paris"
    assert len(provider.latencies) == 2
