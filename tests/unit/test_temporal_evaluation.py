"""Temporal evaluation controls; fixtures are synthetic, never real-data evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.data.ingestion import PaymentDataset
from ringsentinel.evaluation.temporal import EvaluationPlan, LabelFile, ResolvedLabel, evaluate


@pytest.fixture(scope="module")
def control():
    bundle = SyntheticPaymentGenerator(GenerationConfig(transactions=100)).generate()
    data = PaymentDataset(
        schema_version="payments-v1", entities=bundle.entities, events=bundle.events
    )
    plan = EvaluationPlan(
        schema_version="temporal-evaluation-v1",
        data_origin="synthetic-control",
        authorization_confirmed=True,
        label_definition="Synthetic control labels for tests only.",
        validation_start=datetime(2026, 1, 1, tzinfo=UTC),
        test_start=datetime(2026, 1, 16, tzinfo=UTC),
        test_end=datetime(2026, 2, 1, tzinfo=UTC),
        labels_as_of=datetime(2026, 3, 1, tzinfo=UTC),
    )
    ordered = sorted(data.events, key=lambda event: (event.timestamp, event.event_id))
    labels = LabelFile(
        schema_version="resolved-labels-v1",
        labels=tuple(
            ResolvedLabel(
                event_id=event.event_id,
                is_fraud=bool(index % 2),
                resolved_at=event.timestamp + timedelta(minutes=1),
            )
            for index, event in enumerate(ordered)
        ),
    )
    scores = {event.event_id: (index % 10) / 10 for index, event in enumerate(ordered)}
    return data, plan, labels, scores


def test_missing_and_delayed_labels_are_not_assumed_negative(control):
    data, plan, labels, scores = control
    validation_label = next(
        label
        for label in labels.labels
        if plan.validation_start
        <= next(event.timestamp for event in data.events if event.event_id == label.event_id)
        < plan.test_start
    )
    missing = labels.model_copy(
        update={
            "labels": tuple(
                label for label in labels.labels if label.event_id != validation_label.event_id
            )
        }
    )
    report = evaluate(data, missing, plan, scores, 0.5)
    assert report["windows"]["validation"]["unresolved_or_missing"] == 1
    assert report["production_ready"] is False
    assert report["data_origin"] == "synthetic-control"
    delayed = labels.model_copy(
        update={
            "labels": tuple(
                label.model_copy(update={"resolved_at": plan.labels_as_of + timedelta(days=1)})
                if label.event_id == validation_label.event_id
                else label
                for label in labels.labels
            )
        }
    )
    assert (
        evaluate(data, delayed, plan, scores, 0.5)["windows"]["validation"]["unresolved_or_missing"]
        == 1
    )


def test_test_labels_cannot_select_the_threshold(control):
    data, plan, labels, scores = control
    plan = plan.model_copy(update={"threshold_policy": "validation-cost"})
    original = evaluate(data, labels, plan, scores, 0.4)
    test_ids = {event.event_id for event in data.events if event.timestamp >= plan.test_start}
    changed = labels.model_copy(
        update={
            "labels": tuple(
                label.model_copy(update={"is_fraud": not label.is_fraud})
                if label.event_id in test_ids
                else label
                for label in labels.labels
            )
        }
    )
    result = evaluate(data, changed, plan, scores, 0.4)
    assert result["selected_threshold"] == original["selected_threshold"]
    assert result["windows"]["validation"] == original["windows"]["validation"]
    assert result["windows"]["test"] != original["windows"]["test"]
    assert result["windows"]["validation"]["labels_as_of"] == plan.test_start.isoformat()


def test_future_validation_resolution_cannot_tune_historical_threshold(control):
    data, plan, labels, scores = control
    plan = plan.model_copy(update={"threshold_policy": "validation-cost"})
    delayed = labels.model_copy(
        update={
            "labels": tuple(
                label.model_copy(update={"resolved_at": plan.labels_as_of})
                for label in labels.labels
            )
        }
    )
    with pytest.raises(ValueError, match="NO_RESOLVED_LABELS_IN_WINDOW"):
        evaluate(data, delayed, plan, scores, 0.5)


def test_review_capacity_counts_unlabeled_events_and_does_not_tune_on_test(control):
    data, original_plan, labels, original_scores = control
    validation_ids = {
        event.event_id
        for event in data.events
        if original_plan.validation_start <= event.timestamp < original_plan.test_start
    }
    retained = [
        next(
            label
            for label in labels.labels
            if label.event_id in validation_ids and label.is_fraud == fraud
        )
        for fraud in (False, True)
    ]
    partial = labels.model_copy(
        update={
            "labels": tuple(
                label
                for label in labels.labels
                if label.event_id not in validation_ids or label in retained
            )
        }
    )
    scores = {**original_scores, **dict.fromkeys(validation_ids, 0.95)}
    scores[retained[0].event_id] = 0.1
    scores[retained[1].event_id] = 0.6
    plan = EvaluationPlan.model_validate(
        {
            **original_plan.model_dump(),
            "threshold_policy": "validation-cost",
        }
    )
    unconstrained = evaluate(data, partial, plan, scores, 0.4)
    assert unconstrained["selected_threshold"] == 0.6
    assert unconstrained["windows"]["validation"]["selected"]["count"] == 2
    assert (
        unconstrained["windows"]["validation"]["review_load"]["selected"]["flagged_events"]
        == len(validation_ids) - 1
    )
    constrained = EvaluationPlan.model_validate(
        {
            **plan.model_dump(),
            "max_validation_review_fraction": 1 / len(validation_ids),
        }
    )
    report = evaluate(data, partial, constrained, scores, 0.4)
    assert report["selected_threshold"] == 1
    assert report["windows"]["validation"]["review_load"]["selected"]["flagged_events"] == 0
    changed = {
        event_id: value if event_id in validation_ids else 1 for event_id, value in scores.items()
    }
    shifted = evaluate(data, partial, constrained, changed, 0.4)
    assert shifted["selected_threshold"] == report["selected_threshold"]
    assert shifted["windows"]["validation"] == report["windows"]["validation"]
    assert shifted["windows"]["test"]["review_load"]["selected"]["flagged_fraction"] == 1
    assert report["production_ready"] is False
    unlimited = constrained.model_copy(update={"max_validation_review_fraction": 1.0})
    assert evaluate(data, partial, unlimited, scores, 0.4)["selected_threshold"] == 0.6
    # An exact boundary is admissible; score=1 still counts with threshold=1.
    at_boundary = {**scores, retained[1].event_id: 1.0}
    boundary = evaluate(data, partial, constrained, at_boundary, 0.4)
    assert boundary["windows"]["validation"]["selected"]["true_positives"] == 1
    load = boundary["windows"]["validation"]["review_load"]["selected"]
    assert load["flagged_events"] == 1
    assert load["flagged_fraction"] == constrained.max_validation_review_fraction


def test_review_capacity_rejects_infeasible_score_one_ties(control):
    data, plan, labels, scores = control
    plan = EvaluationPlan.model_validate(
        {
            **plan.model_dump(),
            "threshold_policy": "validation-cost",
            "max_validation_review_fraction": 0.0,
        }
    )
    scores = dict.fromkeys(scores, 1.0)
    with pytest.raises(ValueError, match="NO_THRESHOLD_WITHIN_VALIDATION_REVIEW_CAPACITY"):
        evaluate(data, labels, plan, scores, 0.5)


@pytest.mark.parametrize("value", [-0.1, 1.1, "0.5", True, float("nan"), float("inf")])
def test_review_capacity_contract_is_strict(control, value):
    _, plan, _, _ = control
    with pytest.raises(ValidationError):
        EvaluationPlan.model_validate(
            {
                **plan.model_dump(),
                "threshold_policy": "validation-cost",
                "max_validation_review_fraction": value,
            }
        )


def test_frozen_policy_cannot_claim_review_constraint(control):
    _, plan, _, _ = control
    with pytest.raises(ValidationError):
        EvaluationPlan.model_validate(
            {
                **plan.model_dump(),
                "max_validation_review_fraction": 0.5,
            }
        )


@pytest.mark.parametrize("defect", ["duplicate", "unknown", "preceding", "nan", "missing-score"])
def test_label_identity_and_score_failures_are_rejected(control, defect):
    data, plan, labels, scores = control
    if defect == "duplicate":
        labels = labels.model_copy(update={"labels": labels.labels + labels.labels[:1]})
    if defect == "unknown":
        labels = labels.model_copy(
            update={"labels": (labels.labels[0].model_copy(update={"event_id": "unknown"}),)}
        )
    if defect == "preceding":
        labels = labels.model_copy(
            update={
                "labels": (
                    labels.labels[0].model_copy(
                        update={"resolved_at": datetime(2025, 1, 1, tzinfo=UTC)}
                    ),
                )
            }
        )
    if defect == "nan":
        scores = {**scores, next(iter(scores)): float("nan")}
    if defect == "missing-score":
        scores = dict(scores)
        scores.pop(next(iter(scores)))
    with pytest.raises(ValueError):
        evaluate(data, labels, plan, scores, 0.5)


def test_one_class_metrics_are_explicitly_undefined(control):
    data, plan, labels, scores = control
    labels = labels.model_copy(
        update={
            "labels": tuple(label.model_copy(update={"is_fraud": False}) for label in labels.labels)
        }
    )
    report = evaluate(data, labels, plan, scores, 1)
    metrics = report["windows"]["test"]["selected"]
    assert metrics["average_precision"] is None and metrics["recall"] is None
    assert metrics["precision"] is None
    assert sum(item["count"] for item in metrics["raw_score_bins"]) == metrics["count"]


def test_permissions_windows_and_coerced_labels_are_rejected(control):
    _, plan, labels, _ = control
    for patch in (
        {"authorization_confirmed": False},
        {"test_end": plan.test_start},
        {"false_positive_cost": float("inf")},
        {"false_positive_cost": "1"},
        {"label_definition": " " * 10},
        {"test_start": "2026-01-16"},
    ):
        with pytest.raises(ValidationError):
            EvaluationPlan.model_validate({**plan.model_dump(), **patch})
    with pytest.raises(ValidationError):
        ResolvedLabel.model_validate({**labels.labels[0].model_dump(), "is_fraud": "false"})


def test_cli_limits_scoring_to_prefix_and_never_overwrites_reports(
    control, tmp_path, monkeypatch, capsys
):
    import json
    import sys

    import numpy as np

    from ringsentinel.evaluation import temporal

    data, plan, labels, _ = control
    plan = plan.model_copy(update={"test_end": datetime(2026, 1, 28, tzinfo=UTC)})
    missing_id = next(
        event.event_id
        for event in data.events
        if plan.validation_start <= event.timestamp < plan.test_start
    )
    labels = labels.model_copy(
        update={"labels": tuple(label for label in labels.labels if label.event_id != missing_id)}
    )
    inputs = {"payments": data, "labels": labels, "plan": plan}
    for name, value in inputs.items():
        (tmp_path / (name + ".json")).write_text(value.model_dump_json(), encoding="utf-8")
    seen = []

    class FrozenControl:
        feature_names = ("amount_log",)

        def predict_proba(self, table):
            seen.extend(row.timestamp for row in table.rows)
            return np.linspace(0, 1, len(table.rows))

    monkeypatch.setattr(temporal, "load_artifact", lambda *args: (FrozenControl(), 0.4))
    output = tmp_path / "report.json"
    argv = [
        "evaluation",
        "--model",
        str(tmp_path / "trusted-control.joblib"),
        "--model-sha256",
        "a" * 64,
        "--output",
        str(output),
    ]
    for name in inputs:
        argv += ["--" + name, str(tmp_path / (name + ".json"))]
    monkeypatch.setattr(sys, "argv", argv)
    temporal.main()
    report = json.loads(output.read_text())
    assert seen and max(seen) < plan.test_end
    assert report["data_origin"] == "synthetic-control" and not report["production_ready"]
    assert len(report["software"]["source_tree_sha256"]) == 64
    assert set(report["input_sha256"]) == {"payments", "labels", "plan"}
    shift = report["feature_shift"]
    assert shift["validation_events"] == report["windows"]["validation"]["events"]
    assert report["windows"]["validation"]["unresolved_or_missing"] == 1
    assert shift["test_events"] == report["windows"]["test"]["events"]
    assert set(shift["features"]) == {"amount_log"} and shift["labels_used"] is False
    assert data.events[0].event_id not in output.read_text()
    original = output.read_bytes()
    capsys.readouterr()
    with pytest.raises(SystemExit) as error:
        temporal.main()
    assert error.value.code == 2 and output.read_bytes() == original
    text = capsys.readouterr().out
    assert "unavailable" in text and "REPORT_EXISTS" in text and str(tmp_path) not in text


def test_metrics_match_hand_calculated_counts_costs_and_score_boundaries(control):
    from ringsentinel.evaluation.temporal import measurements

    _, plan, _, _ = control
    plan = plan.model_copy(update={"false_positive_cost": 2, "false_negative_cost": 5})
    metrics = measurements([0, 1, 0, 1], [0.1, 0.8, 0.7, 0.4], 0.5, plan)
    assert [
        metrics[key]
        for key in ("true_positives", "false_positives", "false_negatives", "true_negatives")
    ] == [1, 1, 1, 1]
    assert metrics["precision"] == metrics["recall"] == metrics["false_positive_rate"] == 0.5
    assert metrics["relative_error_cost"] == 7
    assert metrics["average_precision"] == pytest.approx(5 / 6)
    assert metrics["brier_score_raw_uncalibrated"] == pytest.approx(0.225)
    boundaries = measurements([0, 1], [0, 1], 1, plan)
    assert (
        boundaries["raw_score_bins"][0]["count"] == boundaries["raw_score_bins"][-1]["count"] == 1
    )
    assert boundaries["brier_score_raw_uncalibrated"] == 0
