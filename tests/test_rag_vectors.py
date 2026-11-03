import pytest

from agenteval.providers import FakeProvider, ProviderError
from agenteval.rag import chunk, validate_vector


def test_chunks_overlap_and_do_not_omit_tail():
    rows = chunk(" ".join(str(i) for i in range(230)))
    assert rows[0].split()[-20:] == rows[1].split()[:20]
    assert rows[-1].split()[-1] == "229"


@pytest.mark.parametrize("vector", [[], [0] * 768, [1] * 767, [float("nan")] * 768])
def test_invalid_vectors_rejected(vector):
    with pytest.raises(ProviderError):
        validate_vector(vector)


async def test_simulated_embeddings_are_normalized_and_repeatable():
    provider = FakeProvider()
    vector = await provider.embed("Paris France")
    assert vector == await provider.embed("Paris France")
    assert sum(x * x for x in vector) == pytest.approx(1)
