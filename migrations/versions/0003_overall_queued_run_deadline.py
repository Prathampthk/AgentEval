"""Overall queued run deadline"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "evaluation_runs", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("evaluation_runs", "deadline_at")
