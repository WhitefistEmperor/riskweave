from __future__ import annotations

import numpy as np

from ringsentinel.evaluation.metrics import evaluate_events, select_f1_threshold


def test_event_metrics_and_threshold_selection() -> None:
    labels = np.asarray([0, 0, 1, 1])
    scores = np.asarray([0.1, 0.2, 0.8, 0.9])

    threshold = select_f1_threshold(labels, scores)
    metrics = evaluate_events(labels, scores, threshold)

    assert 0.2 < threshold <= 0.8
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["pr_auc"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
