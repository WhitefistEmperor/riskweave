"""Shared boosted-tree implementation for fair baseline comparison."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from ringsentinel.features.extractor import FeatureTable


class BoostedTreeDetector:
    """Histogram gradient boosting over an explicit feature allowlist."""

    def __init__(self, feature_names: tuple[str, ...], *, random_state: int) -> None:
        self.feature_names = feature_names
        self.model = HistGradientBoostingClassifier(
            learning_rate=0.07,
            max_iter=160,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=0.5,
            class_weight="balanced",
            random_state=random_state,
        )

    def fit(self, tables: tuple[FeatureTable, ...], labels: tuple[np.ndarray, ...]) -> None:
        matrix = np.concatenate([table.matrix(self.feature_names) for table in tables])
        targets = np.concatenate(labels)
        self.model.fit(matrix, targets)

    def predict_proba(self, table: FeatureTable) -> np.ndarray:
        return self.model.predict_proba(table.matrix(self.feature_names))[:, 1]
