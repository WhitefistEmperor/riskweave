from __future__ import annotations

import hashlib
import json

import pytest

from ringsentinel.data.generator import SyntheticPaymentGenerator, export_dataset, load_dataset
from ringsentinel.data.schema import GenerationConfig
from ringsentinel.data.validation import DatasetValidationError


def test_export_writes_expected_tables_and_valid_checksums(tmp_path) -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=99, transactions=300)).generate()
    checksums = export_dataset(bundle, tmp_path)

    expected = {
        "entities.jsonl",
        "events.jsonl",
        "entity_labels.jsonl",
        "event_labels.jsonl",
        "fraud_rings.json",
        "benign_communities.json",
        "manifest.json",
    }
    assert set(checksums) == expected
    for filename, digest in checksums.items():
        assert hashlib.sha256((tmp_path / filename).read_bytes()).hexdigest() == digest

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest["payment_count"] == 300
    assert len(events) == manifest["payment_count"] + manifest["refund_count"]
    assert manifest["content_sha256"] == bundle.manifest.content_sha256
    assert load_dataset(tmp_path) == bundle


def test_load_rejects_tampered_export(tmp_path) -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=3, transactions=200)).generate()
    export_dataset(bundle, tmp_path)
    with (tmp_path / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")

    with pytest.raises(DatasetValidationError, match="checksum mismatch"):
        load_dataset(tmp_path)
