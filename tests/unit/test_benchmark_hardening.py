from __future__ import annotations

import re
from collections import defaultdict
from statistics import median, quantiles

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import AttackArchetype, EntityType, EventType, GenerationConfig
from ringsentinel.generate import build_parser


def hardened_sample():
    return SyntheticPaymentGenerator(GenerationConfig(seed=42, transactions=1_000)).generate()


def test_default_fraud_event_prevalence_is_between_three_and_seven_percent() -> None:
    bundle = hardened_sample()
    prevalence = sum(label.is_fraud for label in bundle.event_labels) / len(bundle.event_labels)

    assert 0.03 <= prevalence <= 0.07
    assert build_parser().parse_args([]).fraud_ratio == 0.05


def test_fraud_ratio_remains_configurable() -> None:
    low = SyntheticPaymentGenerator(
        GenerationConfig(seed=5, transactions=2_000, fraud_transaction_ratio=0.03)
    ).generate()
    high = SyntheticPaymentGenerator(
        GenerationConfig(seed=5, transactions=2_000, fraud_transaction_ratio=0.10)
    ).generate()

    low_rate = sum(label.is_fraud for label in low.event_labels) / len(low.event_labels)
    high_rate = sum(label.is_fraud for label in high.event_labels) / len(high.event_labels)
    assert high_rate > low_rate


def test_amount_and_account_age_distributions_overlap() -> None:
    bundle = hardened_sample()
    event_labels = {label.subject_id: label for label in bundle.event_labels}
    entity_labels = {label.subject_id: label for label in bundle.entity_labels}
    fraud_amounts = [
        event.amount_minor for event in bundle.events if event_labels[event.event_id].is_fraud
    ]
    benign_amounts = [
        event.amount_minor for event in bundle.events if not event_labels[event.event_id].is_fraud
    ]

    fraud_q1, _, fraud_q3 = quantiles(fraud_amounts, n=4)
    benign_q1, _, benign_q3 = quantiles(benign_amounts, n=4)
    assert min(fraud_q3, benign_q3) > max(fraud_q1, benign_q1)
    assert 0.5 < median(fraud_amounts) / median(benign_amounts) < 2.0

    customers = {
        entity.entity_id: entity
        for entity in bundle.entities
        if entity.entity_type is EntityType.CUSTOMER
    }
    first_event = {}
    for event in bundle.events:
        first_event[event.customer_id] = min(
            event.timestamp, first_event.get(event.customer_id, event.timestamp)
        )
    fraud_ages = [
        (first_event[item] - customer.created_at).total_seconds() / 86_400
        for item, customer in customers.items()
        if item in first_event and entity_labels[item].is_fraud
    ]
    benign_ages = [
        (first_event[item] - customer.created_at).total_seconds() / 86_400
        for item, customer in customers.items()
        if item in first_event and not entity_labels[item].is_fraud
    ]
    fraud_age_q1, _, fraud_age_q3 = quantiles(fraud_ages, n=4)
    benign_age_q1, _, benign_age_q3 = quantiles(benign_ages, n=4)
    assert min(fraud_age_q3, benign_age_q3) > max(fraud_age_q1, benign_age_q1)


def test_raw_ids_attributes_and_timestamps_do_not_encode_targets() -> None:
    bundle = hardened_sample()
    opaque_id = re.compile(r"^[a-z]+_[0-9a-f]{16}$")
    assert all(opaque_id.fullmatch(entity.entity_id) for entity in bundle.entities)
    assert all(opaque_id.fullmatch(event.event_id) for event in bundle.events)
    assert all(opaque_id.fullmatch(event.transaction_id) for event in bundle.events)

    attack_clock_times = {
        (ring.attack_start_time.hour, ring.attack_start_time.minute, ring.attack_start_time.second)
        for ring in bundle.fraud_rings
    }
    assert len(attack_clock_times) == len(bundle.fraud_rings)
    assert any(clock != (0, 0, 0) for clock in attack_clock_times)

    labels = {label.subject_id: label for label in bundle.entity_labels}
    for entity_type in (
        EntityType.CUSTOMER,
        EntityType.CARD,
        EntityType.DEVICE,
        EntityType.IP,
        EntityType.ADDRESS,
        EntityType.MERCHANT,
        EntityType.BANK_ACCOUNT,
    ):
        fraud_shapes = {
            tuple(sorted(entity.attributes))
            for entity in bundle.entities
            if entity.entity_type is entity_type and labels[entity.entity_id].is_fraud
        }
        benign_shapes = {
            tuple(sorted(entity.attributes))
            for entity in bundle.entities
            if entity.entity_type is entity_type and not labels[entity.entity_id].is_fraud
        }
        assert fraud_shapes & benign_shapes


def test_hard_negatives_are_large_varied_and_high_connectivity() -> None:
    bundle = hardened_sample()
    sizes = [len(community.member_customer_ids) for community in bundle.benign_communities]
    assert min(sizes) >= 16
    assert len(set(sizes)) == len(sizes)

    customers_by_entity: defaultdict[str, set[str]] = defaultdict(set)
    for event in bundle.events:
        for entity_id in (
            event.device_id,
            event.ip_id,
            event.address_id,
            event.merchant_id,
        ):
            customers_by_entity[entity_id].add(event.customer_id)
    for community in bundle.benign_communities:
        assert max(len(customers_by_entity[item]) for item in community.shared_entity_ids) >= 6


def test_refund_exposure_counts_each_purchase_once_and_rates_are_labeled() -> None:
    bundle = hardened_sample()
    event_by_id = {event.event_id: event for event in bundle.events}
    refund_ring = next(
        ring for ring in bundle.fraud_rings if ring.archetype is AttackArchetype.REFUND_ABUSE
    )
    fraudulent = [event_by_id[item] for item in refund_ring.fraudulent_event_ids]
    related = [event_by_id[item] for item in refund_ring.related_event_ids]

    assert all(event.event_type is EventType.REFUND for event in fraudulent)
    assert refund_ring.monetary_exposure_minor == sum(event.amount_minor for event in fraudulent)
    assert refund_ring.monetary_exposure_minor < sum(event.amount_minor for event in related)
    assert refund_ring.expected_loss_rate_kind == "synthetic_assumption"
