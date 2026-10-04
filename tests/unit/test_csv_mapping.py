"""Source mapping must preserve causal features and reject ambiguous financial records."""

import csv
import hashlib
import io
import json
import sys

import pytest

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.data import csv_mapping
from ringsentinel.features.extractor import extract_event_features


def encode(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


@pytest.fixture
def control():
    bundle = SyntheticPaymentGenerator(GenerationConfig(transactions=100)).generate()
    mapping = csv_mapping.CsvMapping(
        schema_version="payment-csv-mapping-v1",
        mapping_version="control.1",
        data_origin="synthetic-control",
        authorization_confirmed=True,
        entity_columns={key: "source_" + key for key in sorted(csv_mapping.ENTITY_FIELDS)},
        event_columns={key: "source_" + key for key in sorted(csv_mapping.EVENT_FIELDS)},
    )
    entities = [
        {
            source: row.model_dump(mode="json")[target]
            for target, source in mapping.entity_columns.items()
        }
        for row in bundle.entities
    ]
    events = []
    for event in bundle.events:
        row = event.model_dump(mode="json")
        row["retry_count"] = row["metadata"].get("retry_count", 0)
        events.append(
            {
                source: row[target] if row[target] is not None else ""
                for target, source in mapping.event_columns.items()
            }
        )
    return bundle, mapping, entities, events


def mapped(control):
    _, mapping, entities, events = control
    return csv_mapping.convert(
        encode(entities, list(mapping.entity_columns.values())),
        encode(events, list(mapping.event_columns.values())),
        mapping,
    )


def test_mapping_preserves_ids_units_refunds_and_causal_features(control):
    bundle, _, _, events = control
    events[0]["source_payment_method"] = 'quoted, method "value"'
    parsed = mapped(control)
    assert extract_event_features(parsed).rows == extract_event_features(bundle).rows
    assert [e.event_id for e in parsed.events] == [e.event_id for e in bundle.events]
    assert [e.amount_minor for e in parsed.events] == [e.amount_minor for e in bundle.events]
    assert [e.original_transaction_id for e in parsed.events] == [
        e.original_transaction_id for e in bundle.events
    ]
    assert parsed.events[0].payment_method == events[0]["source_payment_method"]
    assert not hasattr(parsed, "event_labels")


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_minor", "1.01"),
        ("amount_minor", "1e3"),
        ("amount_minor", "-100"),
        ("amount_minor", str(2**63)),
        ("amount_minor", "0"),
        ("timestamp", "2026-01-01T01:00:00"),
        ("timestamp", "1767225600"),
        ("retry_count", "unknown"),
        ("customer_id", "missing"),
        ("card_id", ""),
        ("currency", "inr"),
    ],
)
def test_ambiguous_or_invalid_source_values_fail(control, field, value):
    control[3][0]["source_" + field] = value
    with pytest.raises(ValueError):
        mapped(control)


def test_invalid_refund_duplicate_events_and_mixed_currency_fail(control):
    events = control[3]
    refund = next(row for row in events if row["source_event_type"] == "REFUND")
    saved = refund["source_original_transaction_id"]
    refund["source_original_transaction_id"] = "unknown-payment"
    with pytest.raises(ValueError):
        mapped(control)
    refund["source_original_transaction_id"] = saved
    events.append(events[0].copy())
    with pytest.raises(ValueError):
        mapped(control)
    events.pop()
    # USD on all records for one customer preserves refund identity, but violates isolation.
    customer = events[0]["source_customer_id"]
    for row in events:
        if row["source_customer_id"] == customer:
            row["source_currency"] = "USD"
    with pytest.raises(ValueError, match="currencies"):
        mapped(control)


def test_mapping_is_explicit_and_does_not_copy_unused_label_columns(control):
    _, mapping, entities, events = control
    raw = mapping.model_dump()
    raw["authorization_confirmed"] = "true"
    with pytest.raises(ValueError):
        csv_mapping.CsvMapping.model_validate(raw)
    raw = mapping.model_dump()
    raw["event_columns"]["is_fraud"] = "fraud"
    with pytest.raises(ValueError):
        csv_mapping.CsvMapping.model_validate(raw)
    for row in events:
        row["fraud"] = "PRIVATE-LABEL"
    result = csv_mapping.convert(
        encode(entities, list(mapping.entity_columns.values())),
        encode(events, [*mapping.event_columns.values(), "fraud"]),
        mapping,
    )
    assert "PRIVATE-LABEL" not in result.model_dump_json()


@pytest.mark.parametrize(
    "raw", [b"id,id\nx,y\n", b"id\nx,y\n", b"id\n\n", b'id\n"unterminated', b"id\n\xff\n"]
)
def test_malformed_csv_is_rejected(raw):
    with pytest.raises((ValueError, csv.Error)):
        csv_mapping.records(raw, {"entity_id": "id"}, ",")


def test_cli_provenance_private_output_and_no_overwrite(control, tmp_path, monkeypatch, capsys):
    _, mapping, entities, events = control
    for name, content in (
        ("entities", encode(entities, list(mapping.entity_columns.values()))),
        ("events", encode(events, list(mapping.event_columns.values()))),
        ("mapping", mapping.model_dump_json().encode()),
    ):
        (tmp_path / name).write_bytes(content)
    output = tmp_path / "converted"
    args = ["mapping"]
    for name in ("entities", "events", "mapping"):
        args += ["--" + name, str(tmp_path / name)]
    args += ["--output-directory", str(output)]
    monkeypatch.setattr(sys, "argv", args)
    csv_mapping.main()
    console = capsys.readouterr().out
    report = json.loads((output / "provenance.json").read_text())
    assert (
        report["payments_sha256"]
        == hashlib.sha256((output / "payments.json").read_bytes()).hexdigest()
    )
    assert report["data_origin"] == "synthetic-control" and report["production_ready"] is False
    assert "source_" not in console and str(tmp_path) not in console
    original = (output / "payments.json").read_bytes()
    with pytest.raises(SystemExit) as error:
        csv_mapping.main()
    assert error.value.code == 2
    assert (output / "payments.json").read_bytes() == original
    assert "OUTPUT_EXISTS" in capsys.readouterr().out
    (tmp_path / "events").write_text("PRIVATE INVALID CSV")
    monkeypatch.setattr(sys, "argv", [*args[:-1], str(tmp_path / "invalid-output")])
    with pytest.raises(SystemExit):
        csv_mapping.main()
    assert not (tmp_path / "invalid-output").exists()
    assert "PRIVATE" not in capsys.readouterr().out


def test_csv_bounds_are_enforced(control, monkeypatch):
    monkeypatch.setattr(csv_mapping, "MAX_INPUT_BYTES", 4)
    with pytest.raises(ValueError, match="large"):
        csv_mapping.records(b"id\nabcdef\n", {"entity_id": "id"}, ",")
    monkeypatch.setattr(csv_mapping, "MAX_INPUT_BYTES", 100_000_000)
    monkeypatch.setattr(csv_mapping, "MAX_ROWS", 1)
    with pytest.raises(ValueError, match="limit"):
        csv_mapping.records(b"id\naaa\nbbb\n", {"entity_id": "id"}, ",")
    monkeypatch.setattr(csv_mapping, "MAX_ROWS", 100_000)
    monkeypatch.setattr(csv_mapping, "MAX_OUTPUT_BYTES", 1)
    with pytest.raises(ValueError, match="large"):
        mapped(control)


def test_bom_delimiter_and_quoted_unicode_values():
    rows = csv_mapping.records(
        '\ufeffidentity;type\n"pseudonym;\u03b1";CUSTOMER\n'.encode(),
        {"entity_id": "identity", "entity_type": "type"},
        ";",
    )
    assert rows == [{"entity_id": "pseudonym;\u03b1", "entity_type": "CUSTOMER"}]


def test_failed_output_write_cleans_new_directory(control, tmp_path, monkeypatch, capsys):
    from pathlib import Path

    _, mapping, entities, events = control
    for name, content in (
        ("entities", encode(entities, list(mapping.entity_columns.values()))),
        ("events", encode(events, list(mapping.event_columns.values()))),
        ("mapping", mapping.model_dump_json().encode()),
    ):
        (tmp_path / name).write_bytes(content)
    output = tmp_path / "converted"
    args = ["mapping"]
    for name in ("entities", "events", "mapping"):
        args += ["--" + name, str(tmp_path / name)]
    args += ["--output-directory", str(output)]
    monkeypatch.setattr(sys, "argv", args)
    original = Path.open

    def fail_report(self, *args, **kwargs):
        if self.name == "provenance.json" and args == ("xb",):
            raise OSError("PRIVATE FAILURE")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_report)
    with pytest.raises(SystemExit):
        csv_mapping.main()
    assert not output.exists()
    console = capsys.readouterr().out
    assert "PRIVATE" not in console and str(tmp_path) not in console
