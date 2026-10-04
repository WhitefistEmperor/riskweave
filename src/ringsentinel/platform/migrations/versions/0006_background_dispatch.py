"""Transactional delivery intents and bounded background reconciliation."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_runs", sa.Column("dispatch_state", sa.String(16), nullable=True))
    op.create_table(
        "analysis_dispatches",
        sa.Column("run_id", sa.String(80), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("ticket", sa.String(36), nullable=False),
        sa.Column("budget_month", sa.String(7), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(80)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_code", sa.String(40)),
    )
    op.create_index(
        "ix_analysis_dispatches_next_attempt_at", "analysis_dispatches", ["next_attempt_at"]
    )
    op.create_table(
        "dispatch_budgets",
        sa.Column("month", sa.String(7), primary_key=True),
        sa.Column("starts", sa.Integer(), nullable=False),
    )
    op.create_table(
        "dispatch_schedules",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(80)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("analysis_dispatches")
    op.drop_table("dispatch_budgets")
    op.drop_table("dispatch_schedules")
    op.drop_column("analysis_runs", "dispatch_state")
