"""Real payment ingestion must preserve evidence and never synthesize labels."""

import json

import pytest

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.data.ingestion import PaymentDataset, parse_input, single_currency
from ringsentinel.features.extractor import extract_event_features


@pytest.fixture
def observed():
    bundle = SyntheticPaymentGenerator(GenerationConfig(transactions=100)).generate()
    data = bundle.model_dump(mode="json")
    return bundle, {
        "schema_version": "payments-v1",
        "entities": data["entities"],
        "events": data["events"],
    }


def test_unlabeled_input_preserves_features_without_ground_truth(observed):
    original, data = observed
    parsed = parse_input(json.dumps(data).encode())
    assert isinstance(parsed, PaymentDataset)
    assert not hasattr(parsed, "event_labels")
    assert extract_event_features(parsed).rows == extract_event_features(original).rows


def test_invalid_references_are_rejected(observed):
    _, data = observed
    data["events"][0]["customer_id"] = "unknown-customer"
    with pytest.raises(ValueError, match="missing"):
        parse_input(json.dumps(data).encode())


def test_mixed_currency_is_rejected(observed):
    _, data = observed
    data["events"][0]["currency"] = "USD"
    with pytest.raises(ValueError):
        parse_input(json.dumps(data).encode())


def test_ground_truth_fields_cannot_enter_unlabeled_contract(observed):
    _, data = observed
    data["event_labels"] = []
    with pytest.raises(ValueError):
        parse_input(json.dumps(data).encode())


def test_synthetic_inputs_cannot_bypass_currency_isolation(observed):
    original, _ = observed
    data = original.model_dump(mode="json")
    # Change every USD-linked refund along with its payment, so referential checks pass.
    customer = data["events"][0]["customer_id"]
    for event in data["events"]:
        if event["customer_id"] == customer:
            event["currency"] = "USD"
    with pytest.raises(ValueError, match="currencies separately"):
        parse_input(json.dumps(data).encode())


def test_non_inr_input_preserves_original_minor_units(observed):
    _, data = observed
    for event in data["events"]:
        event["currency"] = "JPY"
    parsed = parse_input(json.dumps(data).encode())
    assert single_currency(parsed) == "JPY"
    assert [event.amount_minor for event in parsed.events] == [
        event["amount_minor"] for event in data["events"]
    ]
