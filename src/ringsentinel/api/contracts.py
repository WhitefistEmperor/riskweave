"""Version-one public contracts. Internal storage keys and execution locks stay private."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from ringsentinel.platform.models import Status


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ErrorDetail(Contract):
    code: str
    message: str
    request_id: str


class ErrorResponse(Contract):
    error: ErrorDetail


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    application_version: str


class ReadinessResponse(Contract):
    status: Literal["ready"] = "ready"
    database: Literal["ready"] = "ready"
    storage: Literal["ready"] = "ready"


class SessionResponse(Contract):
    user_id: str
    authentication_mode: Literal["development"] = "development"
    production_authentication: Literal[False] = False


class InvestigationCreate(Contract):
    name: Annotated[str, Field(min_length=1, max_length=120)]

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not value.strip() or any(not char.isprintable() for char in value):
            raise ValueError("Supply a printable investigation name")
        return value.strip()


class Record(Contract):
    id: str
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def utc_timestamps(cls, value: datetime) -> datetime:
        # SQLite returns naive datetimes; persisted values are always written in UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class InvestigationResponse(Record):
    owner_id: str
    name: str
    status: Status
    source_metadata: dict[str, JsonValue]
    analysis_metadata: dict[str, JsonValue]


class ArtifactResponse(Record):
    investigation_id: str
    original_name: str
    content_type: str
    size_bytes: int
    checksum: str


class RunCreate(Contract):
    artifact_id: Annotated[str, Field(pattern=r"^[a-f0-9-]{36}$")]


class RunResponse(Record):
    investigation_id: str
    artifact_id: str
    status: Status
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message_safe: str | None
    version_metadata: dict[str, str]
    configuration_snapshot: dict[str, JsonValue]
    result_checksum: str | None

    @field_validator("started_at", "completed_at", mode="after")
    @classmethod
    def optional_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return cls.utc_timestamps(value) if value is not None else None


class CandidateResponse(Contract):
    candidate_id: str
    risk_score: float
    first_suspicious_timestamp: datetime
    estimated_exposure_minor: int
    suspicious_relationships: list[str]
    evidence: dict[str, int | float]
    member_entity_ids: list[str]
    related_event_ids: list[str]


class RingMember(Contract):
    entity_id: str
    entity_type: str
    created_at: datetime


class SharedEntity(Contract):
    entity_id: str
    customer_ids: list[str]
    customer_count: int
    event_count: int


class SharedPayout(Contract):
    bank_account_id: str
    merchant_ids: list[str]
    merchant_count: int
    event_count: int


class TimelineEvent(Contract):
    event_id: str
    event_type: str
    transaction_id: str
    timestamp: datetime
    amount_minor: int
    status: str
    customer_id: str
    merchant_id: str
    risk_score: float | None


class Refund(Contract):
    refund_event_id: str
    original_transaction_id: str | None
    timestamp: datetime
    amount_minor: int
    refund_fraction: float | None
    delay_hours: float | None


class RefundPatterns(Contract):
    refund_count: int
    refund_amount_minor: int
    refunds: list[Refund]


class MerchantRelationship(Contract):
    merchant_id: str
    payout_account_id: str
    customer_ids: list[str]
    customer_count: int
    event_count: int


class TemporalActivity(Contract):
    hour: datetime
    event_count: int
    payment_count: int
    refund_count: int
    amount_minor: int
    unique_customers: int


class Exposure(Contract):
    candidate_id: str
    estimated_exposure_minor: int
    definition: str


class MemberBehavior(Contract):
    customer_id: str
    event_count: int
    payment_count: int
    refund_count: int
    total_amount_minor: int
    mean_amount_minor: float
    merchant_count: int
    device_count: int
    ip_count: int
    first_event_at: datetime
    last_event_at: datetime


class EvidenceResponse(Contract):
    get_candidate_ring: CandidateResponse
    get_ring_members: list[RingMember]
    get_shared_devices: list[SharedEntity]
    get_shared_ips: list[SharedEntity]
    get_shared_cards: list[SharedEntity]
    get_shared_addresses: list[SharedEntity]
    get_shared_payout_accounts: list[SharedPayout]
    get_transaction_timeline: list[TimelineEvent]
    get_refund_patterns: RefundPatterns
    get_merchant_relationships: list[MerchantRelationship]
    get_temporal_activity: list[TemporalActivity]
    calculate_exposure: Exposure
    compare_member_behavior: list[MemberBehavior]


class PersistedRing(Contract):
    candidate: CandidateResponse
    queries: EvidenceResponse


class ResultsResponse(Contract):
    schema_version: Literal["1"]
    threshold: float
    event_count: int
    entity_count: int
    model_scope: str
    rings: list[PersistedRing]


class InvestigatorRequest(Contract):
    question: Annotated[str, Field(min_length=1, max_length=1000)]

    @field_validator("question")
    @classmethod
    def meaningful_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Supply a question")
        return value


class Fact(Contract):
    id: str
    text: str
    query: str
    path: str


class EvidenceSource(Contract):
    query: str
    result: JsonValue


class InvestigatorResponse(Contract):
    candidate_id: str
    question: str
    provider: str
    summary_mode: Literal["extractive_computed_facts"]
    statements: list[Fact]
    sources: list[EvidenceSource]
    limitations: list[str]
    warning: str | None
