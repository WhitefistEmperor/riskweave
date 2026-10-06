"""Explicit managed-runtime and trusted-bundle admission before creating a public app."""

import json
import os
import re
from pathlib import Path

from ringsentinel.models.artifact import load_artifact
from ringsentinel.platform.settings import Settings

MODEL_DIRECTORY = Path("deployment/generated-model")


def configure_bundle(root: Path):
    directory = root.resolve() / MODEL_DIRECTORY
    artifact = directory / "network-hgb.joblib"
    manifest = directory / "network-hgb.metadata.json"
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    digest = metadata.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid trusted model manifest")
    configured = os.getenv("RINGSENTINEL_MODEL_ARTIFACT_PATH")
    configured_digest = os.getenv("RINGSENTINEL_MODEL_ARTIFACT_SHA256")
    if (configured and Path(configured).resolve() != artifact) or (
        configured_digest and configured_digest != digest
    ):
        raise ValueError("Configured model differs from the release bundle")
    # Verify digest before executable deserialization and validate compatibility.
    load_artifact(artifact, digest)
    os.environ["RINGSENTINEL_MODEL_ARTIFACT_PATH"] = str(artifact)
    os.environ["RINGSENTINEL_MODEL_ARTIFACT_SHA256"] = digest
    return metadata


def create_vercel_app(root: Path):
    if os.getenv("RINGSENTINEL_ENVIRONMENT") != "production" or not os.getenv(
        "VERCEL_DEPLOYMENT_ID"
    ):
        raise ValueError("The Vercel entry point requires explicit managed production settings")
    configure_bundle(root)
    settings = Settings()
    if (
        settings.execution_mode != "request"
        or settings.background_dispatch != "vercel_workflow"
        or settings.storage_backend != "database"
        or settings.storage_root.resolve() != Path("/tmp/riskweave").resolve()
    ):
        raise ValueError("The Vercel entry point requires managed delivery and disposable scratch")
    from ringsentinel.api.app import create_app

    return create_app(settings=settings)
