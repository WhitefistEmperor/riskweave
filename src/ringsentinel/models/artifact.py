"""Build-owned model artifacts. Uploaded datasets can never choose a model path."""

import hashlib
import io
import json
import platform
from pathlib import Path

import joblib
import sklearn

from ringsentinel.features.extractor import NETWORK_FEATURES, TRANSACTION_FEATURES
from ringsentinel.models.tabular import BoostedTreeDetector


def write_artifact(model: BoostedTreeDetector, threshold: float, path: Path) -> dict:
    metadata = {
        "schema_version": 1,
        "training_seeds": [102, 103, 104],
        "validation_seed": 101,
        "random_state": 105,
        "feature_names": list(model.feature_names),
        "threshold": threshold,
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "scope": "synthetic-trained; uncalibrated; analyst review required",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        joblib.dump({"model": model, "threshold": threshold, "metadata": metadata}, output)
    metadata["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def load_artifact(path: Path, expected_sha256: str) -> tuple[BoostedTreeDetector, float]:
    """Only load an operator-pinned, trusted build artifact; pickle is executable."""
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("Model artifact checksum mismatch")
    artifact = joblib.load(io.BytesIO(content))
    model, threshold, metadata = artifact["model"], artifact["threshold"], artifact["metadata"]
    if (
        metadata["schema_version"] != 1
        or metadata["sklearn_version"] != sklearn.__version__
        or not isinstance(model, BoostedTreeDetector)
        or model.feature_names != TRANSACTION_FEATURES + NETWORK_FEATURES
        or not 0 <= threshold <= 1
    ):
        raise ValueError("Incompatible model artifact")
    return model, float(threshold)


def main():
    import argparse

    from ringsentinel.api.runtime import DemoRuntime

    parser = argparse.ArgumentParser(description="Build the frozen synthetic detector artifact")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model, threshold = DemoRuntime().model_and_threshold
    metadata = write_artifact(model, threshold, args.output)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
