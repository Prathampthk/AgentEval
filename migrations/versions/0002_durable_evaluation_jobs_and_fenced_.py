"""Durable evaluation jobs and fenced results"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR (status <> 'RUNNING' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_job_lease",
        ),
        sa.CheckConstraint(
            "(status IN ('PENDING','RUNNING') AND completed_at IS NULL) OR (status IN ('COMPLETED','FAILED','CANCELED') AND completed_at IS NOT NULL)",
            name="ck_job_completion",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED','CANCELED')", name="ck_job_status"
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempts <= max_attempts",
            name="ck_job_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "dataset_id"],
            ["evaluation_runs.id", "evaluation_runs.dataset_id"],
            name="fk_job_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id", "dataset_id"],
            ["test_cases.id", "test_cases.dataset_id"],
            name="fk_job_case",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "run_id", "test_case_id", "dataset_id", name="uq_job_identity"),
        sa.UniqueConstraint("run_id", "test_case_id", name="uq_job_case"),
    )
    op.create_index(
        "ix_jobs_eligible",
        "evaluation_jobs",
        ["available_at", "id"],
        unique=False,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_jobs_expired",
        "evaluation_jobs",
        ["lease_expires_at"],
        unique=False,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    op.add_column("evaluation_results", sa.Column("job_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint("uq_result_job", "evaluation_results", ["job_id"])
    op.create_foreign_key(
        "fk_result_job",
        "evaluation_results",
        "evaluation_jobs",
        ["job_id", "run_id", "test_case_id", "dataset_id"],
        ["id", "run_id", "test_case_id", "dataset_id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("execution_mode", sa.String(length=16), server_default="sync", nullable=False),
    )
    op.add_column(
        "evaluation_runs", sa.Column("submission_key", sa.String(length=200), nullable=True)
    )
    op.add_column("evaluation_runs", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_run_submission_key", "evaluation_runs", ["submission_key"])

    op.drop_constraint("ck_run_status", "evaluation_runs", type_="check")
    op.drop_constraint("ck_run_outcome", "evaluation_runs", type_="check")
    op.create_check_constraint(
        "ck_run_status", "evaluation_runs", "status IN ('RUNNING','COMPLETED','FAILED','CANCELED')"
    )
    op.create_check_constraint(
        "ck_run_outcome",
        "evaluation_runs",
        "(status = 'RUNNING' AND completed_at IS NULL AND error_category IS NULL) OR "
        "(status = 'COMPLETED' AND completed_at IS NOT NULL AND error_category IS NULL) OR "
        "(status IN ('FAILED','CANCELED') AND completed_at IS NOT NULL AND error_category IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_run_mode", "evaluation_runs", "execution_mode IN ('sync','queued')"
    )
    op.create_check_constraint(
        "ck_submission_hash", "evaluation_runs", "(submission_key IS NULL) = (request_hash IS NULL)"
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM evaluation_runs WHERE execution_mode = 'queued'")
    ):
        raise RuntimeError(
            "Downgrade would discard queued execution history; archive/remove it explicitly first"
        )
    op.drop_constraint("ck_run_mode", "evaluation_runs", type_="check")
    op.drop_constraint("ck_submission_hash", "evaluation_runs", type_="check")
    op.drop_constraint("ck_run_status", "evaluation_runs", type_="check")
    op.drop_constraint("ck_run_outcome", "evaluation_runs", type_="check")
    op.create_check_constraint(
        "ck_run_status", "evaluation_runs", "status IN ('RUNNING','COMPLETED','FAILED')"
    )
    op.create_check_constraint(
        "ck_run_outcome",
        "evaluation_runs",
        "(status = 'RUNNING' AND completed_at IS NULL AND error_category IS NULL) OR "
        "(status = 'COMPLETED' AND completed_at IS NOT NULL AND error_category IS NULL) OR "
        "(status = 'FAILED' AND completed_at IS NOT NULL AND error_category IS NOT NULL)",
    )

    op.drop_constraint("uq_run_submission_key", "evaluation_runs", type_="unique")
    op.drop_column("evaluation_runs", "request_hash")
    op.drop_column("evaluation_runs", "submission_key")
    op.drop_column("evaluation_runs", "execution_mode")
    op.drop_constraint("fk_result_job", "evaluation_results", type_="foreignkey")
    op.drop_constraint("uq_result_job", "evaluation_results", type_="unique")
    op.drop_column("evaluation_results", "job_id")
    op.drop_index(
        "ix_jobs_expired",
        table_name="evaluation_jobs",
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    op.drop_index(
        "ix_jobs_eligible",
        table_name="evaluation_jobs",
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.drop_table("evaluation_jobs")
