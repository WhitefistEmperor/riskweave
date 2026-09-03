"""Cross-record validation for generated datasets."""

from __future__ import annotations

from collections import Counter, defaultdict

from ringsentinel.data.schema import (
    DatasetBundle,
    EntityType,
    EventType,
    PaymentEvent,
    PaymentStatus,
)


class DatasetValidationError(ValueError):
    """Raised when a generated bundle violates the Phase 1 data contract."""


def calculate_ring_exposure(
    events: list[PaymentEvent] | tuple[PaymentEvent, ...],
    fraudulent_event_ids: set[str],
) -> int:
    """Count at-risk value once per original payment, including abusive refunds."""

    payments = {
        event.transaction_id: event for event in events if event.event_type is EventType.PAYMENT
    }
    fraud_refunds: defaultdict[str, int] = defaultdict(int)
    for event in events:
        if event.event_type is EventType.REFUND and event.event_id in fraudulent_event_ids:
            fraud_refunds[event.original_transaction_id or ""] += event.amount_minor

    exposure = 0
    for transaction_id, payment in payments.items():
        refund_amount = min(payment.amount_minor, fraud_refunds.get(transaction_id, 0))
        if refund_amount:
            exposure += refund_amount
        elif payment.event_id in fraudulent_event_ids and payment.status is PaymentStatus.CAPTURED:
            exposure += payment.amount_minor
    return exposure


def validate_dataset(bundle: DatasetBundle) -> None:
    """Validate identity, referential, temporal, and ground-truth invariants."""

    entity_by_id = {entity.entity_id: entity for entity in bundle.entities}
    event_by_id = {event.event_id: event for event in bundle.events}
    if len(entity_by_id) != len(bundle.entities):
        raise DatasetValidationError("duplicate entity_id")
    if len(event_by_id) != len(bundle.events):
        raise DatasetValidationError("duplicate event_id")

    transaction_ids = [
        event.transaction_id for event in bundle.events if event.event_type is EventType.PAYMENT
    ]
    if len(set(transaction_ids)) != len(transaction_ids):
        raise DatasetValidationError("duplicate payment transaction_id")

    expected_types = {
        "customer_id": EntityType.CUSTOMER,
        "merchant_id": EntityType.MERCHANT,
        "card_id": EntityType.CARD,
        "device_id": EntityType.DEVICE,
        "ip_id": EntityType.IP,
        "address_id": EntityType.ADDRESS,
        "merchant_bank_account_id": EntityType.BANK_ACCOUNT,
    }
    payment_by_transaction = {
        event.transaction_id: event
        for event in bundle.events
        if event.event_type is EventType.PAYMENT
    }
    for event in bundle.events:
        for field, expected_type in expected_types.items():
            entity_id = getattr(event, field)
            entity = entity_by_id.get(entity_id)
            if entity is None:
                raise DatasetValidationError(
                    f"{event.event_id} references missing {field}={entity_id}"
                )
            if entity.entity_type is not expected_type:
                raise DatasetValidationError(
                    f"{event.event_id} {field} expected {expected_type}, got {entity.entity_type}"
                )
        if event.timestamp < entity_by_id[event.customer_id].created_at:
            raise DatasetValidationError(f"{event.event_id} predates its customer")
        if event.event_type is EventType.REFUND:
            original = payment_by_transaction.get(event.original_transaction_id or "")
            if original is None:
                raise DatasetValidationError(f"{event.event_id} references missing payment")
            if event.timestamp <= original.timestamp:
                raise DatasetValidationError(f"{event.event_id} does not follow original payment")
            if event.amount_minor > original.amount_minor:
                raise DatasetValidationError(f"{event.event_id} exceeds original payment amount")

    entity_labels = {label.subject_id: label for label in bundle.entity_labels}
    event_labels = {label.subject_id: label for label in bundle.event_labels}
    if set(entity_labels) != set(entity_by_id):
        raise DatasetValidationError("entity labels do not cover every entity exactly once")
    if set(event_labels) != set(event_by_id):
        raise DatasetValidationError("event labels do not cover every event exactly once")

    ring_ids = {ring.ring_id for ring in bundle.fraud_rings}
    if len(ring_ids) != len(bundle.fraud_rings):
        raise DatasetValidationError("duplicate ring_id")
    for ring in bundle.fraud_rings:
        if not ring.member_entity_ids or not ring.fraudulent_event_ids:
            raise DatasetValidationError(f"{ring.ring_id} has incomplete ground truth")
        if not set(ring.member_entity_ids) <= set(entity_by_id):
            raise DatasetValidationError(f"{ring.ring_id} has unknown members")
        if not set(ring.related_event_ids) <= set(event_by_id):
            raise DatasetValidationError(f"{ring.ring_id} has unknown events")
        if not set(ring.fraudulent_event_ids) <= set(ring.related_event_ids):
            raise DatasetValidationError(f"{ring.ring_id} fraudulent events are not related events")
        stages = [stage.starts_at for stage in ring.attack_progression]
        stage_names = {stage.name for stage in ring.attack_progression}
        if stages != sorted(stages) or stages[0] != ring.attack_start_time:
            raise DatasetValidationError(f"{ring.ring_id} attack progression is invalid")
        expected_loss = round(ring.monetary_exposure_minor * ring.expected_loss_rate)
        if ring.expected_loss_minor != expected_loss:
            raise DatasetValidationError(f"{ring.ring_id} expected loss is inconsistent")
        calculated_exposure = calculate_ring_exposure(
            list(event_by_id.values()), set(ring.fraudulent_event_ids)
        )
        if ring.monetary_exposure_minor != calculated_exposure:
            raise DatasetValidationError(f"{ring.ring_id} exposure is inconsistent")
        for entity_id in ring.member_entity_ids:
            label = entity_labels[entity_id]
            if not label.is_fraud or ring.ring_id not in label.ring_ids:
                raise DatasetValidationError(f"{ring.ring_id} member label is inconsistent")
        for event_id in ring.fraudulent_event_ids:
            label = event_labels[event_id]
            if not label.is_fraud or ring.ring_id not in label.ring_ids:
                raise DatasetValidationError(f"{ring.ring_id} event label is inconsistent")
        for event_id in ring.related_event_ids:
            label = event_labels[event_id]
            if label.attack_stage not in stage_names:
                raise DatasetValidationError(f"{ring.ring_id} has an undefined attack stage")

    for community in bundle.benign_communities:
        for customer_id in community.member_customer_ids:
            if entity_labels[customer_id].is_fraud:
                raise DatasetValidationError(
                    f"benign community {community.community_id} contains fraud"
                )
        for entity_id in community.shared_entity_ids:
            if entity_labels[entity_id].is_fraud:
                raise DatasetValidationError(
                    f"benign shared infrastructure {entity_id} is marked fraud"
                )

    counts = Counter(event.event_type for event in bundle.events)
    manifest = bundle.manifest
    actual = (
        len(bundle.entities),
        counts[EventType.PAYMENT],
        counts[EventType.REFUND],
        len(bundle.fraud_rings),
        len(bundle.benign_communities),
    )
    declared = (
        manifest.entity_count,
        manifest.payment_count,
        manifest.refund_count,
        manifest.fraud_ring_count,
        manifest.benign_community_count,
    )
    if actual != declared:
        raise DatasetValidationError(f"manifest counts {declared} do not match actual {actual}")
