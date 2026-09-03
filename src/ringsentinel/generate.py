"""Command-line interface for deterministic dataset generation."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from ringsentinel.data.generator import SyntheticPaymentGenerator, export_dataset
from ringsentinel.data.schema import AttackArchetype, GenerationConfig


class JsonFormatter(logging.Formatter):
    """Emit compact machine-readable logs without mixing them with the result payload."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key in ("seed", "transactions", "entities", "events", "rings", "content_sha256"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--transactions", type=int, default=1_000)
    parser.add_argument("--fraud-ratio", type=float, default=0.05)
    parser.add_argument("--output", type=Path, default=Path("data/generated/latest"))
    parser.add_argument(
        "--scenario",
        action="append",
        choices=[item.value for item in AttackArchetype],
        help="Repeat to select scenarios; defaults to all ten.",
    )
    parser.add_argument("--log-level", default=os.getenv("RINGSENTINEL_LOG_LEVEL", "INFO"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
    selected = (
        tuple(AttackArchetype(item) for item in args.scenario)
        if args.scenario
        else tuple(AttackArchetype)
    )
    config = GenerationConfig(
        seed=args.seed,
        transactions=args.transactions,
        fraud_transaction_ratio=args.fraud_ratio,
        scenarios=selected,
    )
    bundle = SyntheticPaymentGenerator(config).generate()
    export_dataset(bundle, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "entities": bundle.manifest.entity_count,
                "payments": bundle.manifest.payment_count,
                "refunds": bundle.manifest.refund_count,
                "rings": bundle.manifest.fraud_ring_count,
                "content_sha256": bundle.manifest.content_sha256,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
