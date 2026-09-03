from __future__ import annotations

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import AttackArchetype, EventType, GenerationConfig


def generate(seed: int = 42, transactions: int = 500):
    return SyntheticPaymentGenerator(
        GenerationConfig(seed=seed, transactions=transactions)
    ).generate()


def test_generation_is_reproducible_for_same_seed() -> None:
    first = generate()
    second = generate()

    assert first == second
    assert first.manifest.content_sha256 == second.manifest.content_sha256


def test_different_seed_changes_content() -> None:
    assert generate(seed=1).manifest.content_sha256 != generate(seed=2).manifest.content_sha256


def test_requested_payment_count_and_all_scenarios_are_present() -> None:
    bundle = generate(transactions=600)

    payments = [event for event in bundle.events if event.event_type is EventType.PAYMENT]
    assert len(payments) == 600
    assert {ring.archetype for ring in bundle.fraud_rings} == set(AttackArchetype)
    assert all(ring.member_entity_ids for ring in bundle.fraud_rings)
    assert all(ring.fraudulent_event_ids for ring in bundle.fraud_rings)


def test_refund_abuse_has_valid_linked_refunds() -> None:
    bundle = generate()
    refund_ring = next(
        ring for ring in bundle.fraud_rings if ring.archetype is AttackArchetype.REFUND_ABUSE
    )
    event_by_id = {event.event_id: event for event in bundle.events}
    payment_by_transaction = {
        event.transaction_id: event
        for event in bundle.events
        if event.event_type is EventType.PAYMENT
    }
    refunds = [
        event_by_id[event_id]
        for event_id in refund_ring.related_event_ids
        if event_by_id[event_id].event_type is EventType.REFUND
    ]

    assert refunds
    for refund in refunds:
        original = payment_by_transaction[refund.original_transaction_id]
        assert refund.timestamp > original.timestamp
        assert refund.amount_minor <= original.amount_minor


def test_camouflage_is_related_but_not_labeled_as_fraud() -> None:
    bundle = generate()
    camouflage_ring = next(
        ring
        for ring in bundle.fraud_rings
        if ring.archetype is AttackArchetype.ADVERSARIAL_CAMOUFLAGE
    )
    labels = {label.subject_id: label for label in bundle.event_labels}
    camouflage = [
        event_id for event_id in camouflage_ring.related_event_ids if not labels[event_id].is_fraud
    ]

    assert camouflage
    assert not set(camouflage) & set(camouflage_ring.fraudulent_event_ids)
