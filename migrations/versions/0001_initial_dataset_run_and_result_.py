"""Initial dataset run and result persistence"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_dataset_version"),
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("rubric_version", sa.String(length=30), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL AND error_category IS NULL) OR (status = 'COMPLETED' AND completed_at IS NOT NULL AND error_category IS NULL) OR (status = 'FAILED' AND completed_at IS NOT NULL AND error_category IS NOT NULL)",
            name="ck_run_outcome",
        ),
        sa.CheckConstraint("status IN ('RUNNING','COMPLETED','FAILED')", name="ck_run_status"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "dataset_id", name="uq_run_dataset"),
    )
    op.create_index(
        "ix_runs_dataset_created", "evaluation_runs", ["dataset_id", "created_at"], unique=False
    )
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("exact_match", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "external_id", name="uq_case_external_id"),
        sa.UniqueConstraint("id", "dataset_id", name="uq_case_dataset"),
    )
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("correctness", sa.Integer(), nullable=False),
        sa.Column("relevance", sa.Integer(), nullable=False),
        sa.Column("groundedness", sa.Integer(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("exact_match", sa.Boolean(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("generation_latency_ms", sa.Float(), nullable=False),
        sa.Column("judge_latency_ms", sa.Float(), nullable=False),
        sa.Column("generation_input_tokens", sa.Integer(), nullable=True),
        sa.Column("generation_output_tokens", sa.Integer(), nullable=True),
        sa.Column("judge_input_tokens", sa.Integer(), nullable=True),
        sa.Column("judge_output_tokens", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "generation_latency_ms >= 0 AND generation_latency_ms < 'Infinity'::float8 AND judge_latency_ms >= 0 AND judge_latency_ms < 'Infinity'::float8",
            name="ck_latency",
        ),
        sa.CheckConstraint("correctness BETWEEN 0 AND 2", name="ck_correctness"),
        sa.CheckConstraint(
            "generation_input_tokens IS NULL OR generation_input_tokens >= 0",
            name="ck_generation_input_tokens",
        ),
        sa.CheckConstraint(
            "generation_output_tokens IS NULL OR generation_output_tokens >= 0",
            name="ck_generation_output_tokens",
        ),
        sa.CheckConstraint(
            "groundedness IS NULL OR groundedness BETWEEN 0 AND 2", name="ck_groundedness"
        ),
        sa.CheckConstraint(
            "judge_input_tokens IS NULL OR judge_input_tokens >= 0", name="ck_judge_input_tokens"
        ),
        sa.CheckConstraint(
            "judge_output_tokens IS NULL OR judge_output_tokens >= 0", name="ck_judge_output_tokens"
        ),
        sa.CheckConstraint("relevance BETWEEN 0 AND 2", name="ck_relevance"),
        sa.ForeignKeyConstraint(
            ["run_id", "dataset_id"],
            ["evaluation_runs.id", "evaluation_runs.dataset_id"],
            name="fk_result_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id", "dataset_id"],
            ["test_cases.id", "test_cases.dataset_id"],
            name="fk_result_case",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "test_case_id", name="uq_result_case"),
    )


def downgrade():
    op.drop_table("evaluation_results")
    op.drop_table("test_cases")
    op.drop_index("ix_runs_dataset_created", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_table("datasets")
