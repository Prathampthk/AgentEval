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
