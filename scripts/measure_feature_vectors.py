"""Compare every generated feature value against a prior synthetic-control capture."""

import argparse
import hashlib
import inspect
import json
import time
from pathlib import Path

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.data.ingestion import PaymentDataset
from ringsentinel.features.extractor import extract_event_features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Measurement output exists; no overwrite")
    report = dict(
        data_origin="synthetic-control",
        production_ready=False,
        feature_source_sha256=hashlib.sha256(
            Path(inspect.getfile(extract_event_features)).read_bytes()
        ).hexdigest(),
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope="One local extraction per shape/size; not a hosted limit or accuracy test",
        controls=[],
    )
    for count, dense in ((1000, False), (250, True), (500, True)):
        bundle = SyntheticPaymentGenerator(
            GenerationConfig(seed=105, transactions=count)
        ).generate()
        device = min(bundle.events, key=lambda event: (event.timestamp, event.event_id)).device_id
        payments = PaymentDataset(
            schema_version="payments-v1",
            entities=bundle.entities,
            events=tuple(event.model_copy(update={"device_id": device}) for event in bundle.events)
            if dense
            else bundle.events,
        )
        start = time.perf_counter()
        features = extract_event_features(payments)
        feature_seconds = time.perf_counter() - start
        encoded = json.dumps(
            [(row.event_id, row.values) for row in features.rows],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        report["controls"].append(
            dict(
                requested_payments=count,
                dense=dense,
                events=len(features.rows),
                input_sha256=hashlib.sha256(payments.model_dump_json().encode()).hexdigest(),
                feature_sha256=hashlib.sha256(encoded).hexdigest(),
                feature_seconds=feature_seconds,
            )
        )
    if args.compare:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        if (
            baseline.get("data_origin") != "synthetic-control"
            or baseline.get("production_ready") is not False
        ):
            raise ValueError("Requires a synthetic-control baseline")
        for old, new in zip(baseline["controls"], report["controls"], strict=True):
            for field in (
                "requested_payments",
                "dense",
                "events",
                "input_sha256",
                "feature_sha256",
            ):
                if old[field] != new[field]:
                    raise ValueError("Generated input or exact feature vectors differ")
        report["all_feature_vectors_identical"] = True
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(controls=len(report["controls"]), compared=bool(args.compare))))


if __name__ == "__main__":
    main()
