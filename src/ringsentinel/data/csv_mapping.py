"""Private, explicit CSV mapping into the existing unlabeled payment contract."""

import argparse
import csv
import hashlib
import io
import json
import re
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from ringsentinel.data.ingestion import parse_input
from ringsentinel.data.schema import StrictModel

ENTITY_FIELDS = {"entity_id", "entity_type", "created_at"}
EVENT_FIELDS = {
    "event_id",
    "event_type",
    "transaction_id",
    "timestamp",
    "amount_minor",
    "currency",
    "status",
    "customer_id",
    "merchant_id",
    "card_id",
    "device_id",
    "ip_id",
    "address_id",
    "merchant_bank_account_id",
    "original_transaction_id",
    "channel",
    "payment_method",
    "retry_count",
}
MAX_INPUT_BYTES = 100_000_000
MAX_OUTPUT_BYTES = 100_000_000
MAX_ROWS = 100_000


class CsvMapping(StrictModel):
    schema_version: Literal["payment-csv-mapping-v1"]
    mapping_version: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    data_origin: Literal["observed", "synthetic-control"]
    authorization_confirmed: StrictBool
    delimiter: Literal[",", ";", "\t"] = ","
    entity_columns: dict[str, str]
    event_columns: dict[str, str]

    @model_validator(mode="after")
    def explicit_columns(self):
        if self.authorization_confirmed is not True:
            raise ValueError("Authorization declaration required")
        for columns, required in (
            (self.entity_columns, ENTITY_FIELDS),
            (self.event_columns, EVENT_FIELDS),
        ):
            if set(columns) != required:
                raise ValueError("Complete explicit mapping required")
            if len(set(columns.values())) != len(columns) or any(
                not name or name != name.strip() or len(name) > 200 for name in columns.values()
            ):
                raise ValueError("Invalid or reused source columns")
        return self


def records(content, columns, delimiter):
    if len(content) > MAX_INPUT_BYTES:
        raise ValueError("Input too large")
    # UTF-8 BOM is accepted; no encoding guessing, whitespace stripping or row skipping.
    reader = csv.reader(
        io.StringIO(content.decode("utf-8-sig"), newline=""), delimiter=delimiter, strict=True
    )
    header = next(reader, [])
    if not header or len(set(header)) != len(header) or any(not name for name in header):
        raise ValueError("Unique nonempty headers required")
    if not set(columns.values()) <= set(header):
        raise ValueError("Mapped source columns missing")
    positions = {target: header.index(source) for target, source in columns.items()}
    rows = []
    for index, cells in enumerate(reader):
        if index >= MAX_ROWS or len(cells) != len(header):
            raise ValueError("Invalid CSV row shape or limit")
        row = {target: cells[position] for target, position in positions.items()}
        if any(
            not value or value != value.strip()
            for key, value in row.items()
            if key != "original_transaction_id"
        ):
            raise ValueError("Missing or ambiguous mapped value")
        original = row.get("original_transaction_id")
        if original is not None and original != original.strip():
            raise ValueError("Ambiguous original transaction")
        rows.append(row)
    if not rows:
        raise ValueError("Nonempty CSV required")
    return rows


def aware_timestamp(value):
    parsed = datetime.fromisoformat(value)
    if "T" not in value or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Explicit ISO timestamp with timezone required")
    return parsed.isoformat()


def integer(value, minimum, maximum):
    if not re.fullmatch(r"[0-9]{1,19}", value):
        raise ValueError("Integer minor units or count required")
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError("Integer out of bounds")
    return result


def convert(entities_csv: bytes, events_csv: bytes, mapping: CsvMapping):
    entities = records(entities_csv, mapping.entity_columns, mapping.delimiter)
    events = records(events_csv, mapping.event_columns, mapping.delimiter)
    for row in entities:
        row["created_at"] = aware_timestamp(row["created_at"])
    for row in events:
        row["timestamp"] = aware_timestamp(row["timestamp"])
        row["amount_minor"] = integer(row["amount_minor"], 1, 2**63 - 1)
        row["metadata"] = {"retry_count": integer(row.pop("retry_count"), 0, 1_000_000)}
        row["original_transaction_id"] = row["original_transaction_id"] or None
    encoded = json.dumps(
        {"schema_version": "payments-v1", "entities": entities, "events": events},
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ValueError("Output too large")
    # Reuse all currency, identity, duplicate, chronology and refund invariants.
    return parse_input(encoded)


def read_private(path):
    with path.open("rb") as stream:
        content = stream.read(MAX_INPUT_BYTES + 1)
    if len(content) > MAX_INPUT_BYTES:
        raise ValueError("Input too large")
    return content


def main():
    parser = argparse.ArgumentParser(description="Convert private explicitly mapped payment CSVs")
    for name in ("entities", "events", "mapping", "output-directory"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    created = False
    outputs = []
    try:
        if args.output_directory.exists():
            raise FileExistsError
        inputs = {
            name: read_private(getattr(args, name)) for name in ("entities", "events", "mapping")
        }
        mapping = CsvMapping.model_validate_json(inputs["mapping"])
        data = convert(inputs["entities"], inputs["events"], mapping)
        payments = data.model_dump_json().encode() + b"\n"
        if len(payments) > MAX_OUTPUT_BYTES:
            raise ValueError("Output too large")
        report = {
            "schema_version": "payment-csv-provenance-v1",
            "production_ready": False,
            "data_origin": mapping.data_origin,
            "authorization_is_operator_declaration": True,
            "mapping_version": mapping.mapping_version,
            "converter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in inputs.items()},
            "payments_sha256": hashlib.sha256(payments).hexdigest(),
            "entity_count": len(data.entities),
            "event_count": len(data.events),
            "currency": data.events[0].currency,
            "limitations": [
                "No source-system authenticity or permissions independently verified.",
                "No model validation, labels, FX conversion or missing-value imputation.",
                "Source identities must be stable pseudonyms; values are not anonymized.",
            ],
        }
        # Reserve a new directory; never overwrite files or follow an output symlink.
        args.output_directory.mkdir()
        created = True
        for name, content in (
            ("payments.json", payments),
            ("provenance.json", json.dumps(report, indent=2).encode() + b"\n"),
        ):
            path = args.output_directory / name
            with path.open("xb") as stream:
                outputs.append(path)
                stream.write(content)
        print(
            json.dumps(
                {
                    "status": "converted",
                    "production_ready": False,
                    "data_origin": mapping.data_origin,
                }
            )
        )
    except Exception as error:
        if created:
            for path in outputs:
                with suppress(OSError):
                    path.unlink(missing_ok=True)
            with suppress(OSError):
                args.output_directory.rmdir()
        code = "OUTPUT_EXISTS" if isinstance(error, FileExistsError) else "CSV_MAPPING_FAILED"
        print(json.dumps({"status": "unavailable", "code": code}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
