"""Write a validated upload fixture using the unchanged deterministic generator."""

import argparse
from pathlib import Path

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.data.validation import validate_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=105)
    parser.add_argument("--transactions", type=int, default=1000)
    args = parser.parse_args()
    bundle = SyntheticPaymentGenerator(
        GenerationConfig(seed=args.seed, transactions=args.transactions)
    ).generate()
    validate_dataset(bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects existing samples and benchmark artifacts.
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(bundle.model_dump_json())
    print(f"Validated sample: {len(bundle.entities)} entities, {len(bundle.events)} events")


if __name__ == "__main__":
    main()
