from __future__ import annotations

from ringsentinel.experiments.run import run_benchmark


def test_cross_seed_pipeline_keeps_train_validation_and_test_separate() -> None:
    result = run_benchmark((41, 42, 43), transactions=200)

    assert set(result["aggregate"]) == {
        "rules",
        "graph_heuristic",
        "transaction_hgb",
        "network_aware_hgb",
    }
    assert len(result["folds"]) == 12
    for fold in result["folds"]:
        assert fold["test_seed"] != fold["validation_seed"]
        assert fold["test_seed"] not in fold["training_seeds"]
        assert fold["validation_seed"] not in fold["training_seeds"]
        for metric in ("precision", "recall", "f1", "pr_auc", "false_positive_rate"):
            assert 0.0 <= fold[metric] <= 1.0
