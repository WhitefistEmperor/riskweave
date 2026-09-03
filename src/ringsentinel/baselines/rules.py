"""Fixed transaction/customer-history rules with no network inputs."""

from __future__ import annotations

import numpy as np

from ringsentinel.features.extractor import FeatureTable


class RuleBaseline:
    """Transparent risk score from fixed, predeclared transaction-level thresholds."""

    threshold = 0.25

    def predict_proba(self, table: FeatureTable) -> np.ndarray:
        scores = []
        for row in table.rows:
            values = row.values
            score = 0.0
            score += 0.25 if values["account_age_days"] <= 3 else 0.0
            score += 0.30 if values["customer_events_1h"] >= 3 else 0.0
            score += 0.20 if values["customer_events_24h"] >= 6 else 0.0
            score += (
                0.25 if values["is_refund"] and values["customer_refund_ratio_24h"] >= 0.50 else 0.0
            )
            score += 0.10 if values["retry_count"] >= 1 else 0.0
            scores.append(min(1.0, score))
        return np.asarray(scores, dtype=float)
