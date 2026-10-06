"""Private bounded upload staging with idempotent assembly."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "investigation_id", sa.String(80), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("active_slot", sa.String(80), nullable=True),
        sa.Column("previous_status", sa.String(16), nullable=False),
        sa.Column("artifact_id", sa.String(80), sa.ForeignKey("artifacts.id")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("investigation_id", "idempotency_key"),
        sa.UniqueConstraint("active_slot"),
    )
    op.create_index("ix_upload_sessions_investigation_id", "upload_sessions", ["investigation_id"])
    op.create_index("ix_upload_sessions_expires_at", "upload_sessions", ["expires_at"])
    op.create_table(
        "upload_parts",
        sa.Column(
            "upload_id", sa.String(80), sa.ForeignKey("upload_sessions.id"), primary_key=True
        ),
        sa.Column("part_index", sa.Integer(), primary_key=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="upload_part_size"),
    )


def downgrade():
    op.drop_table("upload_parts")
    op.drop_index("ix_upload_sessions_expires_at", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_investigation_id", table_name="upload_sessions")
    op.drop_table("upload_sessions")
