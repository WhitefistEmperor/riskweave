from __future__ import annotations

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import GenerationConfig
from ringsentinel.data.validation import validate_dataset


def test_ground_truth_is_complete_and_internally_consistent() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=7, transactions=400)).generate()
    validate_dataset(bundle)

    entity_labels = {label.subject_id: label for label in bundle.entity_labels}
    event_labels = {label.subject_id: label for label in bundle.event_labels}
    for ring in bundle.fraud_rings:
        assert ring.attack_progression[0].starts_at == ring.attack_start_time
        assert list(ring.attack_progression) == sorted(
            ring.attack_progression, key=lambda stage: stage.starts_at
        )
        assert ring.monetary_exposure_minor > 0
        assert ring.expected_loss_minor == round(
            ring.monetary_exposure_minor * ring.expected_loss_rate
        )
        assert all(entity_labels[item].is_fraud for item in ring.member_entity_ids)
        assert all(event_labels[item].is_fraud for item in ring.fraudulent_event_ids)


def test_dense_benign_communities_remain_non_fraudulent() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=11, transactions=400)).generate()
    labels = {label.subject_id: label for label in bundle.entity_labels}

    assert {item.archetype for item in bundle.benign_communities} == {
        "family",
        "office",
        "hostel",
        "campus",
        "shared_wifi",
        "common_merchant",
    }
    for community in bundle.benign_communities:
        assert len(community.member_customer_ids) >= 6
        assert all(not labels[item].is_fraud for item in community.member_customer_ids)
        assert all(not labels[item].is_fraud for item in community.shared_entity_ids)


def test_raw_features_do_not_leak_ground_truth() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=13, transactions=400)).generate()
    raw_records = [entity.model_dump(mode="json") for entity in bundle.entities]
    raw_records.extend(event.model_dump(mode="json") for event in bundle.events)
    serialized = str(raw_records).lower()

    for forbidden in ("ring_", "fraud", "camouflage", "benign", "scenario"):
        assert forbidden not in serialized
