from __future__ import annotations

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import GenerationConfig
from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    extract_event_features,
)


def test_features_are_causal_and_do_not_read_labels() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=33, transactions=300)).generate()
    full = extract_event_features(bundle)
    cutoff = 100
    truncated_bundle = bundle.model_copy(update={"events": bundle.events[:cutoff]})
    truncated = extract_event_features(truncated_bundle)
    relabeled_bundle = bundle.model_copy(
        update={
            "entity_labels": tuple(
                label.model_copy(update={"is_fraud": not label.is_fraud})
                for label in bundle.entity_labels
            ),
            "event_labels": tuple(
                label.model_copy(update={"is_fraud": not label.is_fraud})
                for label in bundle.event_labels
            ),
        }
    )

    assert truncated.rows == full.rows[:cutoff]
    assert extract_event_features(relabeled_bundle) == full
    forbidden = ("fraud", "ring", "label", "scenario", "archetype")
    assert not any(
        word in name for name in TRANSACTION_FEATURES + NETWORK_FEATURES for word in forbidden
    )


def test_network_features_capture_shared_infrastructure() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=34, transactions=500)).generate()
    table = extract_event_features(bundle)

    assert max(row.values["shared_device_customers"] for row in table.rows) >= 5
    assert max(row.values["shared_ip_customers"] for row in table.rows) >= 5
    assert max(row.values["payout_merchants"] for row in table.rows) >= 3
    assert max(row.values["synchronized_activity_15m"] for row in table.rows) >= 2
