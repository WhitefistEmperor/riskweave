"""Initial persisted investigation schema. Immutable once applied."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def identity():
    return [
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def status():
    return sa.Column(
        "status",
        sa.Enum(
            "created",
            "uploading",
            "queued",
            "running",
            "completed",
            "failed",
            name="status",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )


def upgrade():
    op.create_table("users", *identity())
    op.create_table(
        "investigations",
        *identity(),
        sa.Column("owner_id", sa.String(80), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        status(),
        sa.Column("source_metadata", sa.JSON, nullable=False),
        sa.Column("analysis_metadata", sa.JSON, nullable=False),
    )
    op.create_index("ix_investigations_owner_id", "investigations", ["owner_id"])
    op.create_table(
        "artifacts",
        *identity(),
        sa.Column(
            "investigation_id", sa.String(80), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("original_name", sa.String(200), nullable=False),
        sa.Column("storage_key", sa.String(100), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint("investigation_id", "checksum"),
    )
    op.create_index("ix_artifacts_investigation_id", "artifacts", ["investigation_id"])
    op.create_table(
        "analysis_runs",
        *identity(),
        sa.Column(
            "investigation_id", sa.String(80), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("artifact_id", sa.String(80), sa.ForeignKey("artifacts.id"), nullable=False),
        status(),
        sa.Column("active_slot", sa.String(80), unique=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message_safe", sa.String(200)),
        sa.Column("version_metadata", sa.JSON, nullable=False),
        sa.Column("configuration_snapshot", sa.JSON, nullable=False),
        sa.Column("result_reference", sa.String(100)),
        sa.Column("result_checksum", sa.String(64)),
        sa.UniqueConstraint("investigation_id", "idempotency_key"),
    )
    op.create_index("ix_analysis_runs_investigation_id", "analysis_runs", ["investigation_id"])
    op.create_index("ix_analysis_runs_artifact_id", "analysis_runs", ["artifact_id"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])


def downgrade():
    for table in ("analysis_runs", "artifacts", "investigations", "users"):
        op.drop_table(table)
