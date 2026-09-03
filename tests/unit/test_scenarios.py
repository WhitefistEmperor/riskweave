from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import AttackArchetype, EventType, GenerationConfig


def test_each_attack_archetype_has_its_defining_signal() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=21, transactions=800)).generate()
    events = {event.event_id: event for event in bundle.events}
    labels = {label.subject_id: label for label in bundle.event_labels}
    rings = {ring.archetype: ring for ring in bundle.fraud_rings}

    obvious = [
        events[item] for item in rings[AttackArchetype.OBVIOUS_COORDINATED].related_event_ids
    ]
    assert Counter(event.device_id for event in obvious).most_common(1)[0][1] == len(obvious)
    assert Counter(event.ip_id for event in obvious).most_common(1)[0][1] == len(obvious)

    fragmented = [events[item] for item in rings[AttackArchetype.FRAGMENTED].related_event_ids]
    assert len({event.merchant_id for event in fragmented}) >= 3
    assert len({event.merchant_bank_account_id for event in fragmented}) == 1
    assert len({event.device_id for event in fragmented}) > 3

    slow = [events[item] for item in rings[AttackArchetype.SLOW_BURN].related_event_ids]
    assert max(event.timestamp for event in slow) - min(
        event.timestamp for event in slow
    ) >= timedelta(days=14)

    device_ring = [events[item] for item in rings[AttackArchetype.DEVICE_SHARING].related_event_ids]
    assert len({event.customer_id for event in device_ring}) >= 5
    assert len({event.card_id for event in device_ring}) >= 5
    assert len({event.device_id for event in device_ring}) == 1

    merchants = [
        events[item] for item in rings[AttackArchetype.MERCHANT_COLLUSION].related_event_ids
    ]
    assert len({event.merchant_id for event in merchants}) >= 3
    assert len({event.merchant_bank_account_id for event in merchants}) == 1

    refund_events = [events[item] for item in rings[AttackArchetype.REFUND_ABUSE].related_event_ids]
    assert any(event.event_type is EventType.REFUND for event in refund_events)

    identities = [
        events[item] for item in rings[AttackArchetype.SYNTHETIC_IDENTITIES].related_event_ids
    ]
    assert len({event.customer_id for event in identities}) >= 5
    assert len({event.address_id for event in identities}) == 1

    expansion = rings[AttackArchetype.RING_EXPANSION]
    expansion_stages = {labels[item].attack_stage for item in expansion.related_event_ids}
    assert expansion_stages == {"seed_group", "recruitment", "scaled_attack"}

    cooperating = [
        events[item] for item in rings[AttackArchetype.COOPERATING_RINGS].related_event_ids
    ]
    customer_devices: defaultdict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"separate_operations": set(), "merger": set()}
    )
    for event in cooperating:
        stage = labels[event.event_id].attack_stage
        customer_devices[event.customer_id][stage].add(event.device_id)
    bridged_customers = [
        stages
        for stages in customer_devices.values()
        if stages["separate_operations"] and stages["merger"]
    ]
    assert bridged_customers
    assert all(
        stages["separate_operations"].isdisjoint(stages["merger"]) for stages in bridged_customers
    )

    camouflage = rings[AttackArchetype.ADVERSARIAL_CAMOUFLAGE]
    assert any(not labels[item].is_fraud for item in camouflage.related_event_ids)
    assert any(labels[item].is_fraud for item in camouflage.related_event_ids)
