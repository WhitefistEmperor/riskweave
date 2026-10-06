"""Trusted artifact integrity and reproducible inference."""

import numpy as np
import pytest

from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    EventFeatureRow,
    FeatureTable,
)
from ringsentinel.models.artifact import load_artifact, write_artifact
from ringsentinel.models.tabular import BoostedTreeDetector
from ringsentinel.platform.settings import Settings


def test_model_artifact_roundtrip_and_tamper_rejection(tmp_path):
    from datetime import UTC, datetime

    features = TRANSACTION_FEATURES + NETWORK_FEATURES
    table = FeatureTable(
        tuple(
            EventFeatureRow(str(i), datetime.now(UTC), {name: float(i % 7) for name in features})
            for i in range(60)
        )
    )
    model = BoostedTreeDetector(features, random_state=105)
    model.fit((table,), (np.array([i % 2 for i in range(60)]),))
    path = tmp_path / "model.joblib"
    metadata = write_artifact(model, 0.5, path)
    restored, threshold = load_artifact(path, metadata["sha256"])
    assert threshold == 0.5
    np.testing.assert_array_equal(model.predict_proba(table), restored.predict_proba(table))
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        load_artifact(path, metadata["sha256"])


def test_artifact_configuration_requires_pinned_digest():
    with pytest.raises(ValueError):
        Settings(model_artifact_path="model.joblib")
    with pytest.raises(ValueError):
        Settings(model_artifact_sha256="a" * 64)
