"""Durable private objects and bounded request-scoped execution."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stored_objects",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name="stored_object_size"),
    )
    # Adding columns/indexes directly preserves a populated SQLite parent table.
    # Recreating it would fail or damage existing review foreign-key references.
    op.add_column("analysis_runs", sa.Column("execution_deadline", sa.DateTime(timezone=True)))
    op.add_column("analysis_runs", sa.Column("executor_slot", sa.String(80)))
    op.create_index(
        "uq_analysis_runs_executor_slot", "analysis_runs", ["executor_slot"], unique=True
    )
    op.create_index("ix_analysis_runs_execution_deadline", "analysis_runs", ["execution_deadline"])


def downgrade():
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_index("ix_analysis_runs_execution_deadline")
        batch.drop_index("uq_analysis_runs_executor_slot")
        batch.drop_column("executor_slot")
        batch.drop_column("execution_deadline")
    op.drop_table("stored_objects")
