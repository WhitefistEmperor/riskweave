"""Verified per-fragment metadata; existing results retain legacy reads."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_runs", sa.Column("result_size_bytes", sa.BigInteger(), nullable=True))
    op.create_table(
        "result_fragments",
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("part_index", sa.Integer(), primary_key=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.CheckConstraint("part_index >= 0 AND part_index < 250", name="result_fragment_index"),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 2000000", name="result_fragment_size"),
    )


def downgrade():
    op.drop_table("result_fragments")
    op.drop_column("analysis_runs", "result_size_bytes")
