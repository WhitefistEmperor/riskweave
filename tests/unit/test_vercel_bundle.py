"""Release model admission rejects tampering and accidental local/public configuration."""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    EventFeatureRow,
    FeatureTable,
)
from ringsentinel.models.artifact import write_artifact
from ringsentinel.models.tabular import BoostedTreeDetector
from ringsentinel.platform.vercel_entry import MODEL_DIRECTORY, configure_bundle, create_vercel_app


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("RINGSENTINEL_MODEL_ARTIFACT_PATH", "")
    monkeypatch.setenv("RINGSENTINEL_MODEL_ARTIFACT_SHA256", "")
    features = TRANSACTION_FEATURES + NETWORK_FEATURES
    table = FeatureTable(
        tuple(
            EventFeatureRow(str(i), datetime.now(UTC), {name: float(i % 7) for name in features})
            for i in range(60)
        )
    )
    model = BoostedTreeDetector(features, random_state=105)
    model.fit((table,), (np.array([i % 2 for i in range(60)]),))
    artifact = tmp_path / MODEL_DIRECTORY / "network-hgb.joblib"
    metadata = write_artifact(model, 0.5, artifact)
    return tmp_path, artifact, metadata


def test_bundle_works_without_runtime_retraining_and_preserves_cached_bytes(bundle):
    from ringsentinel.platform.vercel_build import build

    root, artifact, metadata = bundle
    original = artifact.read_bytes()
    assert build(root)["sha256"] == metadata["sha256"]
    assert configure_bundle(root)["sha256"] == metadata["sha256"]
    assert artifact.read_bytes() == original


def test_corrupt_bundle_is_rejected_before_deserialization(bundle, monkeypatch):
    root, artifact, _ = bundle
    artifact.write_bytes(b"not an executable model")
    monkeypatch.setattr(
        "ringsentinel.models.artifact.joblib.load", lambda _: pytest.fail("unpickle")
    )
    with pytest.raises(ValueError, match="checksum"):
        configure_bundle(root)


@pytest.mark.parametrize(
    "name,value",
    [
        ("RINGSENTINEL_MODEL_ARTIFACT_PATH", "another/model.joblib"),
        ("RINGSENTINEL_MODEL_ARTIFACT_SHA256", "f" * 64),
    ],
)
def test_operator_override_cannot_substitute_the_release_model(bundle, monkeypatch, name, value):
    root, _, _ = bundle
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="differs"):
        configure_bundle(root)


def test_incomplete_cache_does_not_retrain_or_replace_existing_artifact(bundle):
    from ringsentinel.platform.vercel_build import build

    root, artifact, _ = bundle
    original = artifact.read_bytes()
    artifact.with_suffix(".metadata.json").unlink()
    with pytest.raises(ValueError, match="Incomplete"):
        build(root)
    assert artifact.read_bytes() == original


def test_entry_point_never_defaults_to_development_identity(tmp_path, monkeypatch):
    monkeypatch.delenv("RINGSENTINEL_ENVIRONMENT", raising=False)
    monkeypatch.setenv("VERCEL_DEPLOYMENT_ID", "test-only-id")
    with pytest.raises(ValueError, match="explicit managed production"):
        create_vercel_app(tmp_path)


def test_production_entry_point_keeps_development_identity_and_demo_disabled(bundle, monkeypatch):
    import importlib

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi.testclient import TestClient

    api_module = importlib.import_module("ringsentinel.api.app")

    original_factory = api_module.create_app
    # This test verifies ASGI security admission, not managed network delivery.
    # Inject transport so it never initializes a cloud SDK world or credentials.
    monkeypatch.setattr(
        api_module,
        "create_app",
        lambda **kwargs: original_factory(**kwargs, workflow_delivery=object()),
    )

    root, _, _ = bundle
    public = jwt.algorithms.RSAAlgorithm.to_jwk(
        rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key(), as_dict=True
    )
    public.update({"kid": "test-only", "use": "sig", "alg": "RS256"})
    keys = root / "public.json"
    keys.write_text(json.dumps({"keys": [public]}))
    for name, value in {
        "RINGSENTINEL_ENVIRONMENT": "production",
        "VERCEL_DEPLOYMENT_ID": "test-only-not-a-real-deployment",
        "WORKFLOW_TARGET_WORLD": "vercel",
        "RINGSENTINEL_EXECUTION_MODE": "request",
        "RINGSENTINEL_STORAGE_BACKEND": "database",
        "RINGSENTINEL_BACKGROUND_DISPATCH": "vercel_workflow",
        "RINGSENTINEL_DISPATCH_CRON_SECRET": "test-only" * 5,
        "RINGSENTINEL_STORAGE_ROOT": "/tmp/riskweave",
        "RINGSENTINEL_STORAGE_LIMIT_BYTES": "1000000",
        "RINGSENTINEL_DATABASE_URL": "postgresql+psycopg://test@127.0.0.1:1/test",
        "RINGSENTINEL_AUTH_MODE": "jwt",
        "RINGSENTINEL_AUTH_JWKS_PATH": str(keys),
        "RINGSENTINEL_AUTH_ISSUER": "https://test-only.invalid",
        "RINGSENTINEL_AUTH_AUDIENCE": "riskweave-test",
        "RINGSENTINEL_DEMO_ENABLED": "false",
        "RINGSENTINEL_FRONTEND_ORIGINS": '["https://test-only.invalid"]',
        "RINGSENTINEL_TRUSTED_HOSTS": '["testserver"]',
        "RINGSENTINEL_ANALYSIS_TIMEOUT_SECONDS": "60",
    }.items():
        monkeypatch.setenv(name, value)
    with TestClient(create_vercel_app(root)) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/overview").status_code == 404
        denied = client.get("/api/v1/session", headers={"X-Development-User": "admin"})
        assert denied.status_code == 401
        assert client.app.state.executor.thread is None


def test_release_configuration_preserves_registry_and_excludes_private_workspaces():
    import tomllib

    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "vercel.json").read_text())
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    assert metadata["tool"]["vercel"]["entrypoint"] == "app:app"
    assert metadata["tool"]["vercel"]["workflows"][0]["entrypoint"] == (
        "ringsentinel.platform.workflows:wf"
    )
    excluded = config["functions"]["**/*.py"]["excludeFiles"]
    assert "work/**" in excluded and "frontend/**" in excluded and "deployment/**" not in excluded
    assert config["crons"][0]["path"] == "/api/v1/operations/reconcile-delivery"
