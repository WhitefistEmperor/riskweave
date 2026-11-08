"""Persist candidate totals without parsing saved evidence on worklist reads."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_runs", sa.Column("candidate_count", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("analysis_runs", "candidate_count")
