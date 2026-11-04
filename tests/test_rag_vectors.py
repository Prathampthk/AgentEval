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


def test_rag_context_budget_preserves_citation_headers_and_discloses_partial_chunk():
    from agenteval.domain import MAX_CONTEXT_CHARACTERS
    from agenteval.rag import bounded_context

    rows = [dict(document_id=str(i), chunk_id=str(i), content="x" * 6000) for i in range(3)]
    context, ids, truncated = bounded_context(rows)
    assert len(context) == MAX_CONTEXT_CHARACTERS
    assert ids == ["0", "1"] and truncated
    assert "[document=0 chunk=0]" in context and "[document=1 chunk=1]" in context
    assert "[document=2" not in context


def test_rag_context_under_budget_is_unchanged():
    from agenteval.rag import bounded_context

    rows = [dict(document_id="d", chunk_id="c", content="Paris")]
    assert bounded_context(rows) == ("[document=d chunk=c] Paris", ["c"], False)
