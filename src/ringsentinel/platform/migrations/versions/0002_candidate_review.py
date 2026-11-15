"""Run-scoped analyst review and append-only application audit history."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_table(
        "candidate_reviews",
        sa.Column("run_id", sa.String(80), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("candidate_id", sa.String(100), primary_key=True),
        sa.Column("disposition", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="review_positive_version"),
        sa.CheckConstraint(
            "disposition IN ('unreviewed', 'investigating', 'escalated', 'dismissed')",
            name="review_disposition",
        ),
    )
    op.create_table(
        "review_audit",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("candidate_id", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(80), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("previous_disposition", sa.String(30), nullable=False),
        sa.Column("disposition", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("note", sa.String(2000), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "candidate_id"],
            ["candidate_reviews.run_id", "candidate_reviews.candidate_id"],
        ),
        sa.UniqueConstraint("run_id", "candidate_id", "version"),
        sa.UniqueConstraint("run_id", "candidate_id", "idempotency_key"),
    )


def downgrade():
    op.drop_table("review_audit")
    op.drop_table("candidate_reviews")
