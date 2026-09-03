"""Deterministic synthetic payment ecosystem generator."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ringsentinel.data.scenarios import ScenarioSpec, scenario_specs
from ringsentinel.data.schema import (
    AttackArchetype,
    AttackStage,
    BenignCommunityGroundTruth,
    DatasetBundle,
    DatasetManifest,
    EntityRecord,
    EntityType,
    EventType,
    FraudRingGroundTruth,
    GenerationConfig,
    PaymentEvent,
    PaymentStatus,
    SubjectLabel,
)
from ringsentinel.data.validation import (
    DatasetValidationError,
    calculate_ring_exposure,
    validate_dataset,
)

LOGGER = logging.getLogger(__name__)
GENERATOR_VERSION = "0.1.1"
SCHEMA_VERSION = "1.1.0"


def _content_sha256(
    entities: tuple[EntityRecord, ...],
    events: tuple[PaymentEvent, ...],
    entity_labels: tuple[SubjectLabel, ...],
    event_labels: tuple[SubjectLabel, ...],
    fraud_rings: tuple[FraudRingGroundTruth, ...],
    benign_communities: tuple[BenignCommunityGroundTruth, ...],
) -> str:
    content = {
        "entities": [item.model_dump(mode="json") for item in entities],
        "events": [item.model_dump(mode="json") for item in events],
        "entity_labels": [item.model_dump(mode="json") for item in entity_labels],
        "event_labels": [item.model_dump(mode="json") for item in event_labels],
        "fraud_rings": [item.model_dump(mode="json") for item in fraud_rings],
        "benign_communities": [item.model_dump(mode="json") for item in benign_communities],
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


class SyntheticPaymentGenerator:
    """Generate a fully labeled payment world from a single configuration and seed."""

    def __init__(self, config: GenerationConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._entities: list[EntityRecord] = []
        self._events: list[PaymentEvent] = []
        self._event_truth: dict[str, tuple[bool, str | None, str | None]] = {}
        self._fraud_entity_rings: defaultdict[str, set[str]] = defaultdict(set)
        self._rings: list[FraudRingGroundTruth] = []
        self._benign_communities: list[BenignCommunityGroundTruth] = []
        self._merchant_bank: dict[str, str] = {}
        self._legitimate_profiles: list[dict[str, str]] = []
        self._legitimate_merchants: list[str] = []

    def generate(self) -> DatasetBundle:
        """Build, label, hash, and validate one deterministic dataset."""

        LOGGER.info(
            "generation_started",
            extra={"seed": self.config.seed, "transactions": self.config.transactions},
        )
        specs = scenario_specs(self.config.scenarios)
        minimum_budgets = {
            spec.archetype: 7 if spec.archetype is AttackArchetype.COOPERATING_RINGS else 5
            for spec in specs
        }
        fraud_payments = max(
            sum(minimum_budgets.values()),
            round(self.config.transactions * self.config.fraud_transaction_ratio),
        )
        fraud_payments = min(fraud_payments, self.config.transactions - 1)
        legitimate_payments = self.config.transactions - fraud_payments

        self._build_legitimate_world(legitimate_payments)
        extra_budget, remainder = divmod(fraud_payments - sum(minimum_budgets.values()), len(specs))
        for index, spec in enumerate(specs):
            payment_budget = minimum_budgets[spec.archetype] + extra_budget
            self._inject_ring(spec, payment_budget + (1 if index < remainder else 0), index)

        bundle = self._finalize_bundle()
        validate_dataset(bundle)
        LOGGER.info(
            "generation_completed",
            extra={
                "entities": len(bundle.entities),
                "events": len(bundle.events),
                "rings": len(bundle.fraud_rings),
                "content_sha256": bundle.manifest.content_sha256,
            },
        )
        return bundle

    def _next_id(self, prefix: str) -> str:
        self._counters[prefix] += 1
        source = f"{self.config.seed}:{prefix}:{self._counters[prefix]}".encode()
        opaque = hashlib.sha256(source).hexdigest()[:16]
        return f"{prefix}_{opaque}"

    def _device_attributes(self) -> dict[str, Any]:
        return {
            "platform": self.rng.choice(("android", "ios", "web")),
            "fingerprint": "synthetic",
        }

    def _ip_attributes(self) -> dict[str, Any]:
        network = self.rng.choice(("192.0.2", "198.51.100", "203.0.113"))
        return {"network": f"{network}.{self.rng.randrange(1, 255)}", "country": "IN"}

    def _address_attributes(self) -> dict[str, Any]:
        return {
            "region": self.rng.choice(("KA", "MH", "DL", "TN", "WB")),
            "synthetic": True,
        }

    def _bank_attributes(self) -> dict[str, Any]:
        return {"bank_code": f"SYN{self.rng.randrange(100):02d}"}

    def _event_metadata(self) -> dict[str, Any]:
        return {
            "checkout_flow": self.rng.choice(("standard", "saved_method")),
            "retry_count": self.rng.randrange(0, 2),
        }

    def _sample_amount(self, *, is_fraud: bool) -> int:
        """Sample strongly overlapping heavy-tailed amounts for both populations."""

        median_minor = 260_000 if is_fraud else 240_000
        amount = round(self.rng.lognormvariate(math.log(median_minor), 1.0))
        return min(10_000_000, max(500, amount))

    def _add_entity(
        self,
        entity_type: EntityType,
        created_at: datetime,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        prefixes = {
            EntityType.CUSTOMER: "cus",
            EntityType.MERCHANT: "mer",
            EntityType.CARD: "card",
            EntityType.DEVICE: "dev",
            EntityType.IP: "ip",
            EntityType.BANK_ACCOUNT: "bank",
            EntityType.ADDRESS: "addr",
        }
        entity_id = self._next_id(prefixes[entity_type])
        self._entities.append(
            EntityRecord(
                entity_id=entity_id,
                entity_type=entity_type,
                created_at=created_at,
                attributes=attributes or {},
            )
        )
        return entity_id

    def _add_payment(
        self,
        profile: dict[str, str],
        merchant_id: str,
        timestamp: datetime,
        amount_minor: int,
        *,
        ring_id: str | None = None,
        is_fraud: bool = False,
        stage: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: PaymentStatus = PaymentStatus.CAPTURED,
    ) -> PaymentEvent:
        event = PaymentEvent(
            event_id=self._next_id("evt"),
            event_type=EventType.PAYMENT,
            transaction_id=self._next_id("txn"),
            timestamp=timestamp,
            amount_minor=amount_minor,
            currency=self.config.currency,
            status=status,
            customer_id=profile["customer_id"],
            merchant_id=merchant_id,
            card_id=profile["card_id"],
            device_id=profile["device_id"],
            ip_id=profile["ip_id"],
            address_id=profile["address_id"],
            merchant_bank_account_id=self._merchant_bank[merchant_id],
            channel=self.rng.choice(("web", "mobile", "sdk")),
            payment_method=self.rng.choice(("card", "upi", "wallet")),
            metadata=metadata or {},
        )
        self._events.append(event)
        self._event_truth[event.event_id] = (is_fraud, ring_id, stage)
        return event

    def _add_refund(
        self,
        original: PaymentEvent,
        timestamp: datetime,
        amount_minor: int,
        ring_id: str | None = None,
        is_fraud: bool = False,
        stage: str | None = None,
    ) -> PaymentEvent:
        event = PaymentEvent(
            event_id=self._next_id("evt"),
            event_type=EventType.REFUND,
            transaction_id=self._next_id("ref"),
            original_transaction_id=original.transaction_id,
            timestamp=timestamp,
            amount_minor=amount_minor,
            currency=original.currency,
            status=PaymentStatus.REFUNDED,
            customer_id=original.customer_id,
            merchant_id=original.merchant_id,
            card_id=original.card_id,
            device_id=original.device_id,
            ip_id=original.ip_id,
            address_id=original.address_id,
            merchant_bank_account_id=original.merchant_bank_account_id,
            channel=original.channel,
            payment_method=original.payment_method,
            metadata={
                "refund_reason": self.rng.choice(
                    ("customer_request", "duplicate", "service_issue", "returned_item")
                )
            },
        )
        self._events.append(event)
        self._event_truth[event.event_id] = (is_fraud, ring_id, stage)
        return event

    def _create_merchant(self, created_at: datetime, *, bank_id: str | None = None) -> str:
        merchant = self._add_entity(
            EntityType.MERCHANT,
            created_at,
            {
                "category": self.rng.choice(("retail", "travel", "services", "digital_goods")),
                "synthetic": True,
            },
        )
        payout = bank_id or self._add_entity(
            EntityType.BANK_ACCOUNT, created_at, self._bank_attributes()
        )
        self._merchant_bank[merchant] = payout
        return merchant

    def _create_customer_profile(
        self,
        created_at: datetime,
        *,
        device_id: str | None = None,
        ip_id: str | None = None,
        address_id: str | None = None,
    ) -> dict[str, str]:
        customer_id = self._add_entity(
            EntityType.CUSTOMER,
            created_at,
            {"country": "IN", "synthetic": True},
        )
        card_id = self._add_entity(
            EntityType.CARD,
            created_at,
            {"network": self.rng.choice(("visa", "mastercard", "rupay")), "tokenized": True},
        )
        device_id = device_id or self._add_entity(
            EntityType.DEVICE,
            created_at,
            self._device_attributes(),
        )
        ip_id = ip_id or self._add_entity(
            EntityType.IP,
            created_at,
            self._ip_attributes(),
        )
        address_id = address_id or self._add_entity(
            EntityType.ADDRESS,
            created_at,
            self._address_attributes(),
        )
        return {
            "customer_id": customer_id,
            "card_id": card_id,
            "device_id": device_id,
            "ip_id": ip_id,
            "address_id": address_id,
        }

    def _build_legitimate_world(self, payment_count: int) -> None:
        created_at = self.config.start_time - timedelta(days=180)
        merchant_count = max(10, min(40, payment_count // 25))
        self._legitimate_merchants = [
            self._create_merchant(
                self.config.start_time - timedelta(days=self.rng.randrange(30, 366))
            )
            for _ in range(merchant_count)
        ]

        scale = 2 if payment_count >= 700 else 1
        community_sizes = {
            "family": 8 * scale,
            "office": 10 * scale,
            "hostel": 12 * scale,
            "campus": 14 * scale,
            "shared_wifi": 9 * scale,
            "common_merchant": 16 * scale,
        }
        customer_count = max(sum(community_sizes.values()), min(3_000, round(payment_count * 0.60)))
        community_infrastructure: dict[str, dict[str, list[str]]] = {}
        infrastructure_shape = {
            "family": {"address_ids": 1, "ip_ids": 1, "device_ids": 2},
            "office": {"address_ids": 0, "ip_ids": 2, "device_ids": 3},
            "hostel": {"address_ids": 1, "ip_ids": 2, "device_ids": 2},
            "campus": {"address_ids": 0, "ip_ids": 3, "device_ids": 3},
            "shared_wifi": {"address_ids": 0, "ip_ids": 2, "device_ids": 2},
            "common_merchant": {"address_ids": 0, "ip_ids": 0, "device_ids": 0},
        }
        for name, shape in infrastructure_shape.items():
            shared = {
                "address_ids": [
                    self._add_entity(EntityType.ADDRESS, created_at, self._address_attributes())
                    for _ in range(shape["address_ids"])
                ],
                "ip_ids": [
                    self._add_entity(EntityType.IP, created_at, self._ip_attributes())
                    for _ in range(shape["ip_ids"])
                ],
                "device_ids": [
                    self._add_entity(EntityType.DEVICE, created_at, self._device_attributes())
                    for _ in range(shape["device_ids"])
                ],
                "merchant_ids": [self._legitimate_merchants[0]]
                if name == "common_merchant"
                else [],
            }
            community_infrastructure[name] = shared

        community_members: defaultdict[str, list[str]] = defaultdict(list)
        for index in range(customer_count):
            offset = 0
            community: str | None = None
            community_member_index = 0
            for name, size in community_sizes.items():
                if offset <= index < offset + size:
                    community = name
                    community_member_index = index - offset
                    break
                offset += size
            shared = community_infrastructure.get(community or "", {})
            device_ids = shared.get("device_ids", [])
            ip_ids = shared.get("ip_ids", [])
            address_ids = shared.get("address_ids", [])
            customer_created = self.config.start_time - timedelta(
                days=self.rng.randrange(1, 181), seconds=self.rng.randrange(86_400)
            )
            profile = self._create_customer_profile(
                customer_created,
                device_id=device_ids[community_member_index % len(device_ids)]
                if device_ids
                else None,
                ip_id=ip_ids[community_member_index % len(ip_ids)] if ip_ids else None,
                address_id=address_ids[community_member_index % len(address_ids)]
                if address_ids
                else None,
            )
            merchant_ids = shared.get("merchant_ids", [])
            if merchant_ids:
                profile["preferred_merchant_id"] = merchant_ids[0]
            self._legitimate_profiles.append(profile)
            if community:
                community_members[community].append(profile["customer_id"])

        for index, name in enumerate(community_sizes, start=1):
            shared_ids = tuple(
                entity_id for pool in community_infrastructure[name].values() for entity_id in pool
            )
            self._benign_communities.append(
                BenignCommunityGroundTruth(
                    community_id=f"BENIGN_{index:03d}",
                    archetype=name,
                    member_customer_ids=tuple(community_members[name]),
                    shared_entity_ids=shared_ids,
                    rationale=f"Legitimate {name} cohort intentionally shares infrastructure.",
                )
            )

        duration_seconds = self.config.duration_days * 86_400
        guaranteed_profiles = list(self._legitimate_profiles)
        self.rng.shuffle(guaranteed_profiles)
        profiles_for_payments = guaranteed_profiles[:payment_count]
        profiles_for_payments.extend(
            self.rng.choice(self._legitimate_profiles)
            for _ in range(payment_count - len(profiles_for_payments))
        )
        legitimate_captures: list[PaymentEvent] = []
        for profile in profiles_for_payments:
            merchant = profile.get("preferred_merchant_id") or self.rng.choice(
                self._legitimate_merchants
            )
            timestamp = self.config.start_time + timedelta(
                seconds=self.rng.randrange(duration_seconds)
            )
            amount = self._sample_amount(is_fraud=False)
            failed = self.rng.random() < 0.035
            payment = self._add_payment(
                profile,
                merchant,
                timestamp,
                amount,
                status=PaymentStatus.FAILED if failed else PaymentStatus.CAPTURED,
                metadata=self._event_metadata(),
            )
            if not failed and timestamp < self.config.start_time + timedelta(
                days=self.config.duration_days - 3
            ):
                legitimate_captures.append(payment)

        benign_refund_count = min(len(legitimate_captures), round(payment_count * 0.02))
        for original in self.rng.sample(legitimate_captures, benign_refund_count):
            self._add_refund(
                original,
                original.timestamp + timedelta(hours=self.rng.randrange(1, 73)),
                round(original.amount_minor * self.rng.uniform(0.4, 1.0)),
            )

    def _inject_ring(self, spec: ScenarioSpec, payment_budget: int, index: int) -> None:
        ring_id = f"RING_{spec.code}01"
        start = self.config.start_time + timedelta(
            days=2 + index * 2,
            hours=self.rng.randrange(24),
            minutes=self.rng.randrange(60),
            seconds=self.rng.randrange(60),
        )
        entity_created = start - timedelta(
            days=self.rng.randrange(30, 241), seconds=self.rng.randrange(86_400)
        )
        member_count = max(5, min(12, payment_budget // 2))

        shared_device = (
            self._add_entity(
                EntityType.DEVICE,
                entity_created,
                self._device_attributes(),
            )
            if spec.archetype
            in {
                AttackArchetype.OBVIOUS_COORDINATED,
                AttackArchetype.DEVICE_SHARING,
                AttackArchetype.ADVERSARIAL_CAMOUFLAGE,
            }
            else None
        )
        shared_ip = (
            self._add_entity(EntityType.IP, entity_created, self._ip_attributes())
            if spec.archetype is AttackArchetype.OBVIOUS_COORDINATED
            else None
        )
        shared_address = (
            self._add_entity(EntityType.ADDRESS, entity_created, self._address_attributes())
            if spec.archetype is AttackArchetype.SYNTHETIC_IDENTITIES
            else None
        )
        shared_bank = (
            self._add_entity(EntityType.BANK_ACCOUNT, entity_created, self._bank_attributes())
            if spec.archetype in {AttackArchetype.FRAGMENTED, AttackArchetype.MERCHANT_COLLUSION}
            else None
        )
        device_pool = (
            [
                self._add_entity(
                    EntityType.DEVICE,
                    entity_created,
                    self._device_attributes(),
                )
                for _ in range(3)
            ]
            if spec.archetype
            in {
                AttackArchetype.SLOW_BURN,
                AttackArchetype.SYNTHETIC_IDENTITIES,
                AttackArchetype.RING_EXPANSION,
                AttackArchetype.COOPERATING_RINGS,
            }
            else []
        )

        merchant_count = (
            3
            if spec.archetype
            in {
                AttackArchetype.FRAGMENTED,
                AttackArchetype.MERCHANT_COLLUSION,
                AttackArchetype.COOPERATING_RINGS,
            }
            else 1
        )
        merchants: list[str] = []
        for _merchant_index in range(merchant_count):
            common_bank = (
                shared_bank
                if spec.archetype
                in {
                    AttackArchetype.FRAGMENTED,
                    AttackArchetype.MERCHANT_COLLUSION,
                }
                else None
            )
            merchants.append(self._create_merchant(entity_created, bank_id=common_bank))

        profiles: list[dict[str, str]] = []
        for member_index in range(member_count):
            kwargs: dict[str, str] = {}
            if spec.archetype is AttackArchetype.OBVIOUS_COORDINATED:
                assert shared_device is not None and shared_ip is not None
                kwargs = {"device_id": shared_device, "ip_id": shared_ip}
            elif spec.archetype is AttackArchetype.SLOW_BURN:
                kwargs = {"device_id": device_pool[member_index % len(device_pool)]}
            elif spec.archetype is AttackArchetype.DEVICE_SHARING:
                assert shared_device is not None
                kwargs = {"device_id": shared_device}
            elif spec.archetype is AttackArchetype.SYNTHETIC_IDENTITIES:
                assert shared_address is not None
                kwargs = {
                    "device_id": device_pool[member_index % len(device_pool)],
                    "address_id": shared_address,
                }
            elif spec.archetype is AttackArchetype.RING_EXPANSION:
                kwargs = {"device_id": device_pool[min(2, member_index * 3 // member_count)]}
            elif spec.archetype is AttackArchetype.COOPERATING_RINGS:
                kwargs = {"device_id": device_pool[0 if member_index < member_count // 2 else 1]}
            customer_created = start - timedelta(
                days=self.rng.randrange(1, 181), seconds=self.rng.randrange(86_400)
            )
            profile = self._create_customer_profile(customer_created, **kwargs)
            profiles.append(profile)

        member_ids = set(merchants)
        member_ids.update(self._merchant_bank[merchant] for merchant in merchants)
        for profile in profiles:
            member_ids.update(profile.values())

        payments: list[PaymentEvent] = []
        related_event_ids: list[str] = []
        fraudulent_event_ids: list[str] = []
        for event_index in range(payment_budget):
            timestamp, stage = self._scenario_time_and_stage(
                spec.archetype, start, event_index, payment_budget
            )
            profile_index = event_index % member_count
            if spec.archetype is AttackArchetype.COOPERATING_RINGS and stage == "merger":
                merger_start = max(1, int(payment_budget * 0.75))
                profile_index = (event_index - merger_start) % member_count
            profile = dict(profiles[profile_index])
            merchant = merchants[event_index % len(merchants)]
            is_fraud = not (
                spec.archetype
                in {AttackArchetype.ADVERSARIAL_CAMOUFLAGE, AttackArchetype.REFUND_ABUSE}
                and (spec.archetype is AttackArchetype.REFUND_ABUSE or event_index % 3 == 1)
            )
            if spec.archetype is AttackArchetype.COOPERATING_RINGS and stage == "merger":
                opposite = 1 if profile_index < member_count // 2 else 0
                profile["device_id"] = device_pool[opposite]
            if spec.archetype is AttackArchetype.ADVERSARIAL_CAMOUFLAGE and is_fraud:
                assert shared_device is not None
                profile["device_id"] = shared_device
            amount = self._sample_amount(is_fraud=is_fraud)
            event = self._add_payment(
                profile,
                merchant,
                timestamp,
                amount,
                ring_id=ring_id,
                is_fraud=is_fraud,
                stage=stage,
                metadata=self._event_metadata(),
            )
            payments.append(event)
            related_event_ids.append(event.event_id)
            member_ids.update(
                {
                    event.customer_id,
                    event.merchant_id,
                    event.card_id,
                    event.device_id,
                    event.ip_id,
                    event.address_id,
                    event.merchant_bank_account_id,
                }
            )
            if is_fraud:
                fraudulent_event_ids.append(event.event_id)

        if spec.archetype is AttackArchetype.REFUND_ABUSE:
            for refund_index, original in enumerate(payments[::2]):
                refund = self._add_refund(
                    original,
                    start + timedelta(days=6, minutes=refund_index * 3),
                    round(original.amount_minor * self.rng.uniform(0.75, 1.0)),
                    ring_id=ring_id,
                    is_fraud=True,
                    stage="refund_wave",
                )
                related_event_ids.append(refund.event_id)
                fraudulent_event_ids.append(refund.event_id)

        for entity_id in member_ids:
            self._fraud_entity_rings[entity_id].add(ring_id)

        stages = self._scenario_stages(spec.archetype, start)
        exposure = calculate_ring_exposure(self._events, set(fraudulent_event_ids))
        self._rings.append(
            FraudRingGroundTruth(
                ring_id=ring_id,
                archetype=spec.archetype,
                description=spec.description,
                member_entity_ids=tuple(sorted(member_ids)),
                related_event_ids=tuple(related_event_ids),
                fraudulent_event_ids=tuple(fraudulent_event_ids),
                attack_start_time=start,
                attack_progression=stages,
                monetary_exposure_minor=exposure,
                expected_loss_minor=round(exposure * spec.synthetic_expected_loss_rate),
                expected_loss_rate=spec.synthetic_expected_loss_rate,
            )
        )

    def _scenario_time_and_stage(
        self,
        archetype: AttackArchetype,
        start: datetime,
        index: int,
        count: int,
    ) -> tuple[datetime, str]:
        fraction = index / max(1, count - 1)
        if archetype is AttackArchetype.OBVIOUS_COORDINATED:
            stage = "activation" if fraction < 0.2 else "synchronized_burst"
            return start + timedelta(minutes=index * 4), stage
        if archetype is AttackArchetype.DEVICE_SHARING:
            stage = "device_reuse" if fraction < 0.2 else "synchronized_burst"
            return start + timedelta(minutes=index * 4), stage
        if archetype is AttackArchetype.FRAGMENTED:
            stage = "subgroup_activation" if fraction < 0.5 else "indirect_coordination"
            return start + timedelta(days=index % 3, minutes=index * 11), stage
        if archetype is AttackArchetype.SLOW_BURN:
            stage = "low_velocity" if fraction < 0.5 else "persistent_activity"
            return start + timedelta(days=15 * fraction), stage
        if archetype is AttackArchetype.MERCHANT_COLLUSION:
            stage = "merchant_activation" if fraction < 0.5 else "shared_payout"
            return start + timedelta(days=5 * fraction), stage
        if archetype is AttackArchetype.REFUND_ABUSE:
            return start + timedelta(days=4 * fraction), "purchase_setup"
        if archetype is AttackArchetype.SYNTHETIC_IDENTITIES:
            stage = "identity_activation" if fraction < 0.5 else "infrastructure_overlap"
            return start + timedelta(days=3 * fraction), stage
        if archetype is AttackArchetype.RING_EXPANSION:
            if fraction < 0.34:
                return start + timedelta(hours=index), "seed_group"
            if fraction < 0.67:
                return start + timedelta(days=3, hours=index), "recruitment"
            return start + timedelta(days=7, hours=index), "scaled_attack"
        if archetype is AttackArchetype.COOPERATING_RINGS:
            if fraction < 0.75:
                return start + timedelta(days=4 * fraction), "separate_operations"
            return start + timedelta(days=7, hours=index), "merger"
        if archetype is AttackArchetype.ADVERSARIAL_CAMOUFLAGE:
            return start + timedelta(
                days=6 * fraction
            ), "attack" if index % 3 != 1 else "camouflage_mix"
        raise AssertionError(f"unsupported archetype: {archetype}")

    @staticmethod
    def _scenario_stages(archetype: AttackArchetype, start: datetime) -> tuple[AttackStage, ...]:
        descriptions = {
            AttackArchetype.OBVIOUS_COORDINATED: ("activation", "synchronized_burst"),
            AttackArchetype.FRAGMENTED: ("subgroup_activation", "indirect_coordination"),
            AttackArchetype.SLOW_BURN: ("low_velocity", "persistent_activity"),
            AttackArchetype.DEVICE_SHARING: ("device_reuse", "synchronized_burst"),
            AttackArchetype.MERCHANT_COLLUSION: ("merchant_activation", "shared_payout"),
            AttackArchetype.REFUND_ABUSE: ("purchase_setup", "refund_wave"),
            AttackArchetype.SYNTHETIC_IDENTITIES: ("identity_activation", "infrastructure_overlap"),
            AttackArchetype.RING_EXPANSION: ("seed_group", "recruitment", "scaled_attack"),
            AttackArchetype.COOPERATING_RINGS: ("separate_operations", "merger"),
            AttackArchetype.ADVERSARIAL_CAMOUFLAGE: ("attack", "camouflage_mix"),
        }[archetype]
        offsets: dict[AttackArchetype, tuple[timedelta, ...]] = {
            AttackArchetype.OBVIOUS_COORDINATED: (timedelta(0), timedelta(minutes=20)),
            AttackArchetype.FRAGMENTED: (timedelta(0), timedelta(days=1)),
            AttackArchetype.SLOW_BURN: (timedelta(0), timedelta(days=7)),
            AttackArchetype.DEVICE_SHARING: (timedelta(0), timedelta(minutes=20)),
            AttackArchetype.MERCHANT_COLLUSION: (timedelta(0), timedelta(days=2)),
            AttackArchetype.REFUND_ABUSE: (timedelta(0), timedelta(days=6)),
            AttackArchetype.SYNTHETIC_IDENTITIES: (timedelta(0), timedelta(days=1)),
            AttackArchetype.RING_EXPANSION: (
                timedelta(0),
                timedelta(days=3),
                timedelta(days=7),
            ),
            AttackArchetype.COOPERATING_RINGS: (timedelta(0), timedelta(days=7)),
            AttackArchetype.ADVERSARIAL_CAMOUFLAGE: (timedelta(0), timedelta(hours=1)),
        }[archetype]
        return tuple(
            AttackStage(
                name=name,
                starts_at=start + offset,
                description=name.replace("_", " "),
            )
            for name, offset in zip(descriptions, offsets, strict=True)
        )

    def _finalize_bundle(self) -> DatasetBundle:
        entities = tuple(sorted(self._entities, key=lambda item: item.entity_id))
        events = tuple(sorted(self._events, key=lambda item: (item.timestamp, item.event_id)))
        entity_labels = tuple(
            SubjectLabel(
                subject_id=entity.entity_id,
                subject_type=entity.entity_type,
                is_fraud=bool(self._fraud_entity_rings[entity.entity_id]),
                ring_ids=tuple(sorted(self._fraud_entity_rings[entity.entity_id])),
            )
            for entity in entities
        )
        event_labels = tuple(
            SubjectLabel(
                subject_id=event.event_id,
                subject_type=EntityType.REFUND
                if event.event_type is EventType.REFUND
                else EntityType.TRANSACTION,
                is_fraud=self._event_truth[event.event_id][0],
                ring_ids=(self._event_truth[event.event_id][1],)
                if self._event_truth[event.event_id][1]
                else (),
                attack_stage=self._event_truth[event.event_id][2],
            )
            for event in events
        )
        rings = tuple(sorted(self._rings, key=lambda item: item.ring_id))
        communities = tuple(sorted(self._benign_communities, key=lambda item: item.community_id))
        payment_count = sum(event.event_type is EventType.PAYMENT for event in events)
        refund_count = len(events) - payment_count
        manifest = DatasetManifest(
            schema_version=SCHEMA_VERSION,
            generator_version=GENERATOR_VERSION,
            seed=self.config.seed,
            generated_at=self.config.start_time + timedelta(days=self.config.duration_days),
            config=self.config.model_dump(mode="json"),
            entity_count=len(entities),
            payment_count=payment_count,
            refund_count=refund_count,
            fraud_ring_count=len(rings),
            benign_community_count=len(communities),
            content_sha256=_content_sha256(
                entities, events, entity_labels, event_labels, rings, communities
            ),
        )
        return DatasetBundle(
            entities=entities,
            events=events,
            entity_labels=entity_labels,
            event_labels=event_labels,
            fraud_rings=rings,
            benign_communities=communities,
            manifest=manifest,
        )


def export_dataset(bundle: DatasetBundle, output_dir: Path) -> dict[str, str]:
    """Write stable JSON/JSONL tables and return per-file SHA-256 checksums."""

    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_tables = {
        "entities.jsonl": bundle.entities,
        "events.jsonl": bundle.events,
        "entity_labels.jsonl": bundle.entity_labels,
        "event_labels.jsonl": bundle.event_labels,
    }
    for filename, records in jsonl_tables.items():
        text = "".join(
            json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
        (output_dir / filename).write_text(text, encoding="utf-8", newline="\n")

    json_documents = {
        "fraud_rings.json": [item.model_dump(mode="json") for item in bundle.fraud_rings],
        "benign_communities.json": [
            item.model_dump(mode="json") for item in bundle.benign_communities
        ],
        "manifest.json": bundle.manifest.model_dump(mode="json"),
    }
    for filename, document in json_documents.items():
        (output_dir / filename).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )

    checksums = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output_dir.glob("*.json*"))
        if path.name != "checksums.sha256"
    }
    checksum_text = "".join(f"{digest}  {filename}\n" for filename, digest in checksums.items())
    (output_dir / "checksums.sha256").write_text(checksum_text, encoding="ascii", newline="\n")
    return checksums


def load_dataset(input_dir: Path) -> DatasetBundle:
    """Load an exported dataset and revalidate checksums and semantic invariants."""

    required = {
        "entities.jsonl",
        "events.jsonl",
        "entity_labels.jsonl",
        "event_labels.jsonl",
        "fraud_rings.json",
        "benign_communities.json",
        "manifest.json",
    }
    checksum_path = input_dir / "checksums.sha256"
    if not checksum_path.is_file():
        raise DatasetValidationError("missing checksums.sha256")
    declared_checksums = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, filename = line.split("  ", maxsplit=1)
        declared_checksums[filename] = digest
    if set(declared_checksums) != required:
        raise DatasetValidationError("checksum manifest has missing or unexpected files")
    for filename, expected in declared_checksums.items():
        path = input_dir / filename
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise DatasetValidationError(f"checksum mismatch for {filename}")

    def read_jsonl(
        filename: str, model: type[EntityRecord] | type[PaymentEvent] | type[SubjectLabel]
    ):
        return tuple(
            model.model_validate_json(line)
            for line in (input_dir / filename).read_text(encoding="utf-8").splitlines()
            if line
        )

    entities = read_jsonl("entities.jsonl", EntityRecord)
    events = read_jsonl("events.jsonl", PaymentEvent)
    entity_labels = read_jsonl("entity_labels.jsonl", SubjectLabel)
    event_labels = read_jsonl("event_labels.jsonl", SubjectLabel)
    rings = tuple(
        FraudRingGroundTruth.model_validate(item)
        for item in json.loads((input_dir / "fraud_rings.json").read_text(encoding="utf-8"))
    )
    communities = tuple(
        BenignCommunityGroundTruth.model_validate(item)
        for item in json.loads((input_dir / "benign_communities.json").read_text(encoding="utf-8"))
    )
    manifest = DatasetManifest.model_validate_json(
        (input_dir / "manifest.json").read_text(encoding="utf-8")
    )
    bundle = DatasetBundle(
        entities=entities,
        events=events,
        entity_labels=entity_labels,
        event_labels=event_labels,
        fraud_rings=rings,
        benign_communities=communities,
        manifest=manifest,
    )
    validate_dataset(bundle)
    actual_content_hash = _content_sha256(
        entities, events, entity_labels, event_labels, rings, communities
    )
    if actual_content_hash != manifest.content_sha256:
        raise DatasetValidationError("canonical content hash mismatch")
    return bundle
