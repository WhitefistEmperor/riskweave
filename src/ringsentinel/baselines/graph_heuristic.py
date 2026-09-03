"""Fixed network heuristic baseline without model fitting or ground truth."""

from __future__ import annotations

import numpy as np

from ringsentinel.features.extractor import FeatureTable


class GraphHeuristicBaseline:
    """Score sharing, payout reuse, synchronization, and refund-network behavior."""

    threshold = 0.50

    def predict_proba(self, table: FeatureTable) -> np.ndarray:
        scores = []
        for row in table.rows:
            values = row.values
            score = 0.0
            score += 0.25 if values["infrastructure_customer_max"] >= 5 else 0.0
            score += 0.25 if values["multi_shared_neighbor_count"] >= 2 else 0.0
            score += 0.25 if values["payout_merchants"] >= 2 else 0.0
            score += 0.20 if values["synchronized_activity_15m"] >= 4 else 0.0
            score += 0.20 if values["device_refund_ratio_24h"] >= 0.40 else 0.0
            score += 0.10 if values["customer_component_size"] >= 5 else 0.0
            scores.append(min(1.0, score))
        return np.asarray(scores, dtype=float)
