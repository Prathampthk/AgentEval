"""PostgreSQL mappings. Schema changes must use Alembic migrations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_dataset_version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "external_id", name="uq_case_external_id"),
        UniqueConstraint("id", "dataset_id", name="uq_case_dataset"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"))
    external_id: Mapped[str] = mapped_column(String(100))
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    exact_match: Mapped[bool] = mapped_column(Boolean)


class Run(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint("id", "dataset_id", name="uq_run_dataset"),
        CheckConstraint(
            "status IN ('RUNNING','COMPLETED','FAILED','CANCELED')", name="ck_run_status"
        ),
        CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL AND error_category IS NULL) OR "
            "(status = 'COMPLETED' AND completed_at IS NOT NULL AND error_category IS NULL) OR "
            "(status IN ('FAILED','CANCELED') AND completed_at IS NOT NULL AND error_category IS NOT NULL)",
            name="ck_run_outcome",
        ),
        UniqueConstraint("submission_key", name="uq_run_submission_key"),
        CheckConstraint("execution_mode IN ('sync','queued')", name="ck_run_mode"),
        CheckConstraint(
            "(submission_key IS NULL) = (request_hash IS NULL)", name="ck_submission_hash"
        ),
        Index("ix_runs_dataset_created", "dataset_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"))
    execution_mode: Mapped[str] = mapped_column(String(16), server_default="sync")
    submission_key: Mapped[str | None] = mapped_column(String(200))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    rubric_version: Mapped[str] = mapped_column(String(30), default="v1")
    simulated: Mapped[bool] = mapped_column(Boolean)
    configuration: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_category: Mapped[str | None] = mapped_column(String(100))


class Result(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint("run_id", "test_case_id", name="uq_result_case"),
        UniqueConstraint("job_id", name="uq_result_job"),
        ForeignKeyConstraint(
            ["job_id", "run_id", "test_case_id", "dataset_id"],
            [
                "evaluation_jobs.id",
                "evaluation_jobs.run_id",
                "evaluation_jobs.test_case_id",
                "evaluation_jobs.dataset_id",
            ],
            name="fk_result_job",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["run_id", "dataset_id"],
            ["evaluation_runs.id", "evaluation_runs.dataset_id"],
            ondelete="CASCADE",
            name="fk_result_run",
        ),
        ForeignKeyConstraint(
            ["test_case_id", "dataset_id"],
            ["test_cases.id", "test_cases.dataset_id"],
            ondelete="RESTRICT",
            name="fk_result_case",
        ),
        CheckConstraint("correctness BETWEEN 0 AND 2", name="ck_correctness"),
        CheckConstraint("relevance BETWEEN 0 AND 2", name="ck_relevance"),
        CheckConstraint(
            "groundedness IS NULL OR groundedness BETWEEN 0 AND 2", name="ck_groundedness"
        ),
        CheckConstraint(
            "generation_latency_ms >= 0 AND generation_latency_ms < 'Infinity'::float8 AND "
            "judge_latency_ms >= 0 AND judge_latency_ms < 'Infinity'::float8",
            name="ck_latency",
        ),
        *(
            CheckConstraint(f"{field} IS NULL OR {field} >= 0", name=f"ck_{field}")
            for field in (
                "generation_input_tokens",
                "generation_output_tokens",
                "judge_input_tokens",
                "judge_output_tokens",
            )
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column()
    dataset_id: Mapped[UUID] = mapped_column()
    test_case_id: Mapped[UUID] = mapped_column()
    job_id: Mapped[UUID | None] = mapped_column()
    answer: Mapped[str] = mapped_column(Text)
    correctness: Mapped[int] = mapped_column(Integer)
    relevance: Mapped[int] = mapped_column(Integer)
    groundedness: Mapped[int | None] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)
    exact_match: Mapped[bool | None] = mapped_column(Boolean)
    passed: Mapped[bool] = mapped_column(Boolean)
    generation_latency_ms: Mapped[float] = mapped_column(Float)
    judge_latency_ms: Mapped[float] = mapped_column(Float)
    generation_input_tokens: Mapped[int | None] = mapped_column(Integer)
    generation_output_tokens: Mapped[int | None] = mapped_column(Integer)
    judge_input_tokens: Mapped[int | None] = mapped_column(Integer)
    judge_output_tokens: Mapped[int | None] = mapped_column(Integer)


class Job(Base):
    __tablename__ = "evaluation_jobs"
    __table_args__ = (
        UniqueConstraint("run_id", "test_case_id", name="uq_job_case"),
        UniqueConstraint("id", "run_id", "test_case_id", "dataset_id", name="uq_job_identity"),
        ForeignKeyConstraint(
            ["run_id", "dataset_id"],
            ["evaluation_runs.id", "evaluation_runs.dataset_id"],
            name="fk_job_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["test_case_id", "dataset_id"],
            ["test_cases.id", "test_cases.dataset_id"],
            name="fk_job_case",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED','CANCELED')", name="ck_job_status"
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempts <= max_attempts",
            name="ck_job_attempts",
        ),
        CheckConstraint(
            "(status = 'RUNNING' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'RUNNING' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_job_lease",
        ),
        CheckConstraint(
            "(status IN ('PENDING','RUNNING') AND completed_at IS NULL) OR "
            "(status IN ('COMPLETED','FAILED','CANCELED') AND completed_at IS NOT NULL)",
            name="ck_job_completion",
        ),
        Index(
            "ix_jobs_eligible", "available_at", "id", postgresql_where=text("status = 'PENDING'")
        ),
        Index("ix_jobs_expired", "lease_expires_at", postgresql_where=text("status = 'RUNNING'")),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column()
    dataset_id: Mapped[UUID] = mapped_column()
    test_case_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))
