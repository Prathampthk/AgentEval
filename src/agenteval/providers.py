"""Small async provider contract and an explicitly simulated implementation."""

from typing import Protocol

from agenteval.domain import GenerationInput, JudgeInput, JudgeResponse, Judgment, TextResponse


class ProviderError(Exception):
    def __init__(self, category: str, retryable: bool = False):
        self.category = category
        self.retryable = retryable
        super().__init__(category)


class Provider(Protocol):
    name: str
    model: str
    simulated: bool

    async def generate(self, data: GenerationInput) -> TextResponse: ...

    async def judge(self, data: JudgeInput) -> JudgeResponse: ...


class FakeProvider:
    name = "fake"
    model = "context-echo-v1"
    simulated = True
    embedding_model = "hash-bag-v1-768"

    async def embed(self, text: str) -> list[float]:
        import hashlib
        import math
        import re

        vector = [0.0] * 768
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % 768
            vector[index] += 1
        length = math.sqrt(sum(v * v for v in vector))
        if not length:
            raise ProviderError("empty_embedding_input")
        return [value / length for value in vector]

    async def generate(self, data: GenerationInput) -> TextResponse:
        return TextResponse(text=data.context or "No context supplied.")

    async def judge(self, data: JudgeInput) -> JudgeResponse:
        correct = data.expected_answer.casefold() in data.answer.casefold()
        return JudgeResponse(
            judgment=Judgment(
                correctness=2 if correct else 0,
                relevance=2 if correct else 0,
                groundedness=(2 if data.answer == data.context else 0) if data.context else None,
                explanation="SIMULATED: substring check only; this is not a semantic AI judgment.",
            )
        )
