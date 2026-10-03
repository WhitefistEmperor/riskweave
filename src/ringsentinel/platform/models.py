"""Portable relational metadata; large inputs/results live behind storage references."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Status(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def status_column():
    return mapped_column(
        Enum(
            Status,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Identity, Base):
    __tablename__ = "users"


class Investigation(Identity, Base):
    __tablename__ = "investigations"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[Status] = status_column()
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class Artifact(Identity, Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("investigation_id", "checksum"),)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(200))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    checksum: Mapped[str] = mapped_column(String(64))


class AnalysisRun(Identity, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (UniqueConstraint("investigation_id", "idempotency_key"),)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), index=True)
    status: Mapped[Status] = status_column()
    # Portable unique nullable slot: at most one queued/running run per investigation.
    active_slot: Mapped[str | None] = mapped_column(String(80), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message_safe: Mapped[str | None] = mapped_column(String(200))
    version_metadata: Mapped[dict] = mapped_column(JSON)
    configuration_snapshot: Mapped[dict] = mapped_column(JSON)
    result_reference: Mapped[str | None] = mapped_column(String(100))
    result_checksum: Mapped[str | None] = mapped_column(String(64))


class ReviewDisposition(StrEnum):
    UNREVIEWED = "unreviewed"
    INVESTIGATING = "investigating"
    ESCALATED = "escalated"
    DISMISSED = "dismissed"


class CandidateReview(Base):
    __tablename__ = "candidate_reviews"
    __table_args__ = (
        CheckConstraint("version > 0", name="review_positive_version"),
        CheckConstraint(
            "disposition IN ('unreviewed', 'investigating', 'escalated', 'dismissed')",
            name="review_disposition",
        ),
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    disposition: Mapped[str] = mapped_column(String(30))
    version: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewAudit(Base):
    """Append-only in application flows; no editing endpoint exists."""

    __tablename__ = "review_audit"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "candidate_id"],
            ["candidate_reviews.run_id", "candidate_reviews.candidate_id"],
        ),
        UniqueConstraint("run_id", "candidate_id", "version"),
        UniqueConstraint("run_id", "candidate_id", "idempotency_key"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(80))
    candidate_id: Mapped[str] = mapped_column(String(100))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    previous_disposition: Mapped[str] = mapped_column(String(30))
    disposition: Mapped[str] = mapped_column(String(30))
    version: Mapped[int]
    note: Mapped[str] = mapped_column(String(2000))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
