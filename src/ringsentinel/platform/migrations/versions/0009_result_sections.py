"""Targeted immutable result sections; legacy results retain verified fallback."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_runs", sa.Column("candidate_index", sa.JSON(), nullable=True))
    op.create_table(
        "result_sections",
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("candidate_id", sa.String(100), primary_key=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("byte_offset", sa.BigInteger(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.CheckConstraint("byte_offset >= 0 AND size_bytes > 0", name="result_section_range"),
    )


def downgrade():
    op.drop_table("result_sections")
    op.drop_column("analysis_runs", "candidate_index")
