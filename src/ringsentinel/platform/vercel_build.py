"""Build a release-owned synthetic detector; never connects to a case database."""

from pathlib import Path

from ringsentinel.models.artifact import load_artifact, write_artifact
from ringsentinel.platform.vercel_entry import MODEL_DIRECTORY


def build(root: Path):
    import hashlib
    import json

    directory = root.resolve() / MODEL_DIRECTORY
    artifact = directory / "network-hgb.joblib"
    manifest = directory / "network-hgb.metadata.json"
    if artifact.exists() or manifest.exists():
        if not artifact.is_file() or not manifest.is_file():
            raise ValueError("Incomplete cached model bundle; use a fresh build workspace")
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        load_artifact(artifact, metadata["sha256"])
        return metadata
    from ringsentinel.api.runtime import DemoRuntime

    model, threshold = DemoRuntime().model_and_threshold
    metadata = write_artifact(model, threshold, artifact)
    load_artifact(artifact, metadata["sha256"])
    # No mutable data directory, schema migration or environment-secret access.
    return {**metadata, "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(build(Path.cwd()))
