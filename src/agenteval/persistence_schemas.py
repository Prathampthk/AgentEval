"""Public contracts for immutable datasets and persisted, request-scoped runs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from agenteval.domain import EvaluationResult, StrictModel


class DatasetCase(StrictModel):
    external_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=4000)
    expected_answer: str = Field(min_length=1, max_length=4000)
    context: str = Field(default="", max_length=12000)
    exact_match: bool = False


class DatasetCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    cases: list[DatasetCase] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_cases(self):
        ids = [case.external_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("external_id must be unique within a dataset")
        return self


class DatasetView(DatasetCreate):
    id: UUID
    content_hash: str
    created_at: datetime


class RunCreate(StrictModel):
    dataset_id: UUID
    prompt: str = Field(default="Answer the question using the supplied context.", max_length=2000)


class RunView(StrictModel):
    id: UUID
    dataset_id: UUID
    status: Literal["RUNNING", "COMPLETED", "FAILED", "CANCELED"]
    execution_mode: Literal["sync", "queued"]
    provider: str
    model: str
    rubric_version: Literal["v1"]
    simulated: bool
    configuration: dict
    created_at: datetime
    completed_at: datetime | None
    error_category: str | None
    results: list[EvaluationResult]


class JobView(StrictModel):
    id: UUID
    run_id: UUID
    test_case_id: UUID
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELED"]
    attempts: int
    max_attempts: int
    available_at: datetime
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    lease_expires_at: datetime | None
    last_error: str | None
