"""Validated evaluation data; no HTTP or provider SDK dependencies."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvaluationRequest(StrictModel):
    dataset_name: str = Field(min_length=1, max_length=100)
    dataset_version: str = Field(min_length=1, max_length=100)
    test_case_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=4000)
    expected_answer: str = Field(min_length=1, max_length=4000)
    context: str = Field(default="", max_length=12000)
    prompt: str = Field(default="Answer the question using the supplied context.", max_length=2000)
    exact_match: bool = False


class GenerationInput(StrictModel):
    """Deliberately excludes the answer key and evaluation instructions."""

    question: str
    context: str
    prompt: str


class JudgeInput(StrictModel):
    question: str
    expected_answer: str
    context: str
    answer: str


class Judgment(StrictModel):
    correctness: int = Field(strict=True, ge=0, le=2)
    relevance: int = Field(strict=True, ge=0, le=2)
    groundedness: int | None = Field(default=None, strict=True, ge=0, le=2)
    explanation: str = Field(min_length=1, max_length=4000)


class Usage(StrictModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class TextResponse(StrictModel):
    text: str = Field(min_length=1, max_length=16000)
    usage: Usage = Field(default_factory=Usage)


class JudgeResponse(StrictModel):
    judgment: Judgment
    usage: Usage = Field(default_factory=Usage)


class EvaluationResult(StrictModel):
    dataset_name: str
    dataset_version: str
    test_case_id: str
    provider: str
    model: str
    rubric_version: Literal["v1"] = "v1"
    answer: str
    judgment: Judgment
    exact_match: bool | None
    passed: bool
    generation_latency_ms: float
    judge_latency_ms: float
    generation_usage: Usage
    judge_usage: Usage
    simulated: bool
