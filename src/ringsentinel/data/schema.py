"""Validated schemas for the Phase 1 synthetic payment world."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields to keep datasets versionable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EntityType(StrEnum):
    CUSTOMER = "CUSTOMER"
    MERCHANT = "MERCHANT"
    CARD = "CARD"
    DEVICE = "DEVICE"
    IP = "IP"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    ADDRESS = "ADDRESS"
    TRANSACTION = "TRANSACTION"
    REFUND = "REFUND"


class EdgeType(StrEnum):
    CUSTOMER_USES_CARD = "CUSTOMER_USES_CARD"
    CUSTOMER_USES_DEVICE = "CUSTOMER_USES_DEVICE"
    CUSTOMER_CONNECTS_FROM_IP = "CUSTOMER_CONNECTS_FROM_IP"
    CUSTOMER_LOCATED_AT_ADDRESS = "CUSTOMER_LOCATED_AT_ADDRESS"
    CUSTOMER_BUYS_FROM_MERCHANT = "CUSTOMER_BUYS_FROM_MERCHANT"
    TRANSACTION_USES_CARD = "TRANSACTION_USES_CARD"
    TRANSACTION_FROM_DEVICE = "TRANSACTION_FROM_DEVICE"
    TRANSACTION_PAID_TO_MERCHANT = "TRANSACTION_PAID_TO_MERCHANT"
    MERCHANT_PAYS_OUT_TO_BANK_ACCOUNT = "MERCHANT_PAYS_OUT_TO_BANK_ACCOUNT"
    REFUND_OF_TRANSACTION = "REFUND_OF_TRANSACTION"


class EventType(StrEnum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"


class PaymentStatus(StrEnum):
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class AttackArchetype(StrEnum):
    OBVIOUS_COORDINATED = "obvious_coordinated"
    FRAGMENTED = "fragmented"
    SLOW_BURN = "slow_burn"
    DEVICE_SHARING = "device_sharing"
    MERCHANT_COLLUSION = "merchant_collusion"
    REFUND_ABUSE = "refund_abuse"
    SYNTHETIC_IDENTITIES = "synthetic_identities"
    RING_EXPANSION = "ring_expansion"
    COOPERATING_RINGS = "cooperating_rings"
    ADVERSARIAL_CAMOUFLAGE = "adversarial_camouflage"


class EntityRecord(StrictModel):
    entity_id: str = Field(min_length=3)
    entity_type: EntityType
    created_at: AwareDatetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class PaymentEvent(StrictModel):
    event_id: str = Field(min_length=3)
    event_type: EventType
    transaction_id: str = Field(min_length=3)
    timestamp: AwareDatetime
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    status: PaymentStatus
    customer_id: str
    merchant_id: str
    card_id: str
    device_id: str
    ip_id: str
    address_id: str
    merchant_bank_account_id: str
    original_transaction_id: str | None = None
    channel: str
    payment_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_refund_link(self) -> PaymentEvent:
        if self.event_type is EventType.REFUND and not self.original_transaction_id:
            raise ValueError("refunds require original_transaction_id")
        if self.event_type is EventType.PAYMENT and self.original_transaction_id is not None:
            raise ValueError("payments cannot have original_transaction_id")
        return self


class SubjectLabel(StrictModel):
    subject_id: str
    subject_type: EntityType
    is_fraud: bool
    ring_ids: tuple[str, ...] = ()
    attack_stage: str | None = None


class AttackStage(StrictModel):
    name: str
    starts_at: AwareDatetime
    description: str


class FraudRingGroundTruth(StrictModel):
    ring_id: str
    archetype: AttackArchetype
    description: str
    member_entity_ids: tuple[str, ...]
    related_event_ids: tuple[str, ...]
    fraudulent_event_ids: tuple[str, ...]
    attack_start_time: AwareDatetime
    attack_progression: tuple[AttackStage, ...]
    monetary_exposure_minor: int = Field(ge=0)
    expected_loss_minor: int = Field(ge=0)
    expected_loss_rate: float = Field(ge=0, le=1)
    expected_loss_rate_kind: Literal["synthetic_assumption"] = "synthetic_assumption"


class BenignCommunityGroundTruth(StrictModel):
    community_id: str
    archetype: str
    member_customer_ids: tuple[str, ...]
    shared_entity_ids: tuple[str, ...]
    rationale: str


class GenerationConfig(StrictModel):
    seed: int = 42
    transactions: int = Field(default=1_000, ge=100)
    fraud_transaction_ratio: float = Field(default=0.05, ge=0.01, le=0.30)
    start_time: AwareDatetime = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    duration_days: int = Field(default=30, ge=14, le=365)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    scenarios: tuple[AttackArchetype, ...] = tuple(AttackArchetype)

    @model_validator(mode="after")
    def scenarios_must_be_unique(self) -> GenerationConfig:
        if not self.scenarios:
            raise ValueError("at least one scenario is required")
        if len(self.scenarios) != len(set(self.scenarios)):
            raise ValueError("scenarios must be unique")
        if self.transactions < len(self.scenarios) * 5:
            raise ValueError("transactions must allow at least five payments per scenario")
        return self


class DatasetManifest(StrictModel):
    schema_version: str
    generator_version: str
    seed: int
    generated_at: AwareDatetime
    config: dict[str, Any]
    entity_count: int
    payment_count: int
    refund_count: int
    fraud_ring_count: int
    benign_community_count: int
    content_sha256: str


class DatasetBundle(StrictModel):
    entities: tuple[EntityRecord, ...]
    events: tuple[PaymentEvent, ...]
    entity_labels: tuple[SubjectLabel, ...]
    event_labels: tuple[SubjectLabel, ...]
    fraud_rings: tuple[FraudRingGroundTruth, ...]
    benign_communities: tuple[BenignCommunityGroundTruth, ...]
    manifest: DatasetManifest
