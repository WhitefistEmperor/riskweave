"""Explicit unlabeled payment input, separate from synthetic benchmark ground truth."""

import json
from typing import Literal

from ringsentinel.data.schema import DatasetBundle, EntityRecord, PaymentEvent, StrictModel
from ringsentinel.data.validation import validate_payment_records


class PaymentDataset(StrictModel):
    schema_version: Literal["payments-v1"]
    entities: tuple[EntityRecord, ...]
    events: tuple[PaymentEvent, ...]


def parse_input(content: bytes) -> DatasetBundle | PaymentDataset:
    data = json.loads(content)
    if isinstance(data, dict) and data.get("schema_version") == "payments-v1":
        bundle = PaymentDataset.model_validate(data)
        if not bundle.events:
            raise ValueError("Empty payment dataset")
        validate_payment_records(bundle.entities, bundle.events)
        single_currency(bundle)
        return bundle
    from ringsentinel.data.validation import validate_dataset

    bundle = DatasetBundle.model_validate(data)
    validate_dataset(bundle)
    if not bundle.events:
        raise ValueError("Empty dataset")
    single_currency(bundle)
    return bundle


def single_currency(bundle: DatasetBundle | PaymentDataset) -> str:
    currencies = {event.currency for event in bundle.events}
    if len(currencies) != 1:
        raise ValueError("Analyze currencies separately; no implicit currency conversion")
    return next(iter(currencies))
