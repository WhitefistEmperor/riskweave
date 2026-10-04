"""Private temporal evaluation of a frozen model; never a production approval."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Literal

import numpy as np
import sklearn
from pydantic import AwareDatetime, Field, StrictBool, ValidationError, model_validator
from sklearn.metrics import average_precision_score

from ringsentinel import __version__
from ringsentinel.data.ingestion import PaymentDataset, parse_input, single_currency
from ringsentinel.data.schema import StrictModel
from ringsentinel.evaluation.feature_drift import diagnostics
from ringsentinel.features.extractor import extract_event_features
from ringsentinel.models.artifact import load_artifact


class ResolvedLabel(StrictModel):
    event_id: str = Field(min_length=3)
    is_fraud: StrictBool
    resolved_at: AwareDatetime


class LabelFile(StrictModel):
    schema_version: Literal["resolved-labels-v1"]
    labels: tuple[ResolvedLabel, ...]


class EvaluationPlan(StrictModel):
    schema_version: Literal["temporal-evaluation-v1"]
    data_origin: Literal["observed", "synthetic-control"]
    authorization_confirmed: StrictBool
    label_definition: str = Field(min_length=10, max_length=1000)
    validation_start: AwareDatetime
    test_start: AwareDatetime
    test_end: AwareDatetime
    labels_as_of: AwareDatetime
    threshold_policy: Literal["frozen", "validation-cost"] = "frozen"
    false_positive_cost: float = Field(default=1, gt=0, allow_inf_nan=False, strict=True)
    false_negative_cost: float = Field(default=1, gt=0, allow_inf_nan=False, strict=True)

    @model_validator(mode="after")
    def admitted(self):
        if len(self.label_definition.strip()) < 10:
            raise ValueError("Meaningful label definition required")
        if not self.authorization_confirmed:
            raise ValueError("Authorization declaration required")
        if not self.validation_start < self.test_start < self.test_end <= self.labels_as_of:
            raise ValueError("Invalid temporal window order")
        return self


def measurements(labels, scores, threshold, plan):
    labels, scores = np.asarray(labels, dtype=int), np.asarray(scores, dtype=float)
    predicted = scores >= threshold
    tp = int(np.sum(predicted & (labels == 1)))
    fp = int(np.sum(predicted & (labels == 0)))
    fn = int(np.sum(~predicted & (labels == 1)))
    tn = int(np.sum(~predicted & (labels == 0)))
    bins = []
    for index in range(10):
        mask = (scores >= index / 10) & ((scores < (index + 1) / 10) if index < 9 else True)
        count = int(np.sum(mask))
        bins.append(
            dict(
                lower=index / 10,
                upper=(index + 1) / 10,
                count=count,
                mean_score=float(np.mean(scores[mask])) if count else None,
                fraud_fraction=float(np.mean(labels[mask])) if count else None,
            )
        )
    return dict(
        count=len(labels),
        positives=tp + fn,
        negatives=tn + fp,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        false_positive_rate=fp / (fp + tn) if fp + tn else None,
        average_precision=float(average_precision_score(labels, scores))
        if len(set(labels)) == 2
        else None,
        brier_score_raw_uncalibrated=float(np.mean((scores - labels) ** 2)),
        relative_error_cost=fp * plan.false_positive_cost + fn * plan.false_negative_cost,
        raw_score_bins=bins,
    )


def evaluate(
    data: PaymentDataset,
    label_file: LabelFile,
    plan: EvaluationPlan,
    score_by_event: dict[str, float],
    frozen_threshold: float,
):
    """Join labels after frozen predictions; select an optional threshold on validation only."""
    event_by_id = {event.event_id: event for event in data.events}
    label_by_id = {}
    for label in label_file.labels:
        if label.event_id in label_by_id or label.event_id not in event_by_id:
            raise ValueError("INVALID_LABEL_IDENTITY")
        if label.resolved_at < event_by_id[label.event_id].timestamp:
            raise ValueError("LABEL_PRECEDES_EVENT")
        label_by_id[label.event_id] = label
    expected = {event.event_id for event in data.events if event.timestamp < plan.test_end}
    if set(score_by_event) != expected or not 0 <= frozen_threshold <= 1:
        raise ValueError("INVALID_SCORE_IDENTITY")
    if any(not np.isfinite(value) or not 0 <= value <= 1 for value in score_by_event.values()):
        raise ValueError("INVALID_SCORE_VALUE")

    windows = {}
    for name, start, end in (
        ("validation", plan.validation_start, plan.test_start),
        ("test", plan.test_start, plan.test_end),
    ):
        events = [event for event in data.events if start <= event.timestamp < end]
        label_cutoff = (
            plan.test_start
            if name == "validation" and plan.threshold_policy == "validation-cost"
            else plan.labels_as_of
        )
        covered = [
            event
            for event in events
            if event.event_id in label_by_id
            and label_by_id[event.event_id].resolved_at <= label_cutoff
        ]
        if not covered:
            raise ValueError("NO_RESOLVED_LABELS_IN_WINDOW")
        windows[name] = dict(
            events=events,
            covered=covered,
            label_cutoff=label_cutoff,
            labels=[int(label_by_id[event.event_id].is_fraud) for event in covered],
            scores=[score_by_event[event.event_id] for event in covered],
        )
    validation = windows["validation"]
    threshold = frozen_threshold
    if plan.threshold_policy == "validation-cost":
        if len(set(validation["labels"])) != 2:
            raise ValueError("THRESHOLD_SELECTION_REQUIRES_BOTH_CLASSES")
        choices = sorted(set([*np.linspace(0, 1, 101), frozen_threshold]))
        y = np.asarray(validation["labels"], dtype=int)
        scores = np.asarray(validation["scores"], dtype=float)
        threshold = float(
            min(
                choices,
                key=lambda value: (
                    int(np.sum((scores >= value) & (y == 0))) * plan.false_positive_cost
                    + int(np.sum((scores < value) & (y == 1))) * plan.false_negative_cost,
                    -value,
                ),
            )
        )
    reports = {}
    for name, window in windows.items():
        reports[name] = dict(
            labels_as_of=window["label_cutoff"].isoformat(),
            events=len(window["events"]),
            resolved_labels=len(window["covered"]),
            unresolved_or_missing=len(window["events"]) - len(window["covered"]),
            label_coverage=len(window["covered"]) / len(window["events"]),
            frozen=measurements(window["labels"], window["scores"], frozen_threshold, plan),
            selected=measurements(window["labels"], window["scores"], threshold, plan),
        )
        reports[name]["event_type_groups"] = {
            group: measurements(
                [
                    label_by_id[event.event_id].is_fraud
                    for event in window["covered"]
                    if event.event_type.value == group
                ],
                [
                    score_by_event[event.event_id]
                    for event in window["covered"]
                    if event.event_type.value == group
                ],
                threshold,
                plan,
            )
            for group in sorted({event.event_type.value for event in window["covered"]})
        }
    customers = [
        {event.customer_id for event in windows[name]["events"]} for name in ("validation", "test")
    ]
    return dict(
        schema_version="temporal-evaluation-report-v1",
        production_ready=False,
        data_origin=plan.data_origin,
        authorization_is_operator_declaration=True,
        currency=single_currency(data),
        frozen_threshold=frozen_threshold,
        selected_threshold=threshold,
        threshold_policy=plan.threshold_policy,
        validation_test_customer_overlap=len(customers[0] & customers[1]),
        windows=reports,
        limitations=[
            "Frozen synthetic-trained detector; no calibration or retraining performed.",
            "Resolved-label metrics do not establish accuracy on missing/unresolved labels.",
            "Shared customers measure returning-customer behavior, not unseen-customer transfer.",
            "Relative error costs are operator assumptions, not measured monetary loss.",
            "Historical availability of the model and mappings has not been established.",
            "No ring-level validation, confidence intervals or production approval provided.",
        ],
    )


def read_private(path):
    with path.open("rb") as stream:
        content = stream.read(100_000_001)
    if len(content) > 100_000_000:
        raise ValueError("INPUT_TOO_LARGE")
    return content


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trusted frozen model offline")
    for name in ("payments", "labels", "plan", "model", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError
        inputs = {
            name: read_private(getattr(args, name)) for name in ("payments", "labels", "plan")
        }
        data = parse_input(inputs["payments"])
        if not isinstance(data, PaymentDataset):
            raise ValueError("UNLABELED_PAYMENT_INPUT_REQUIRED")
        labels = LabelFile.model_validate_json(inputs["labels"])
        plan = EvaluationPlan.model_validate_json(inputs["plan"])
        scoped = data.model_copy(
            update={
                "events": tuple(event for event in data.events if event.timestamp < plan.test_end)
            }
        )
        model, threshold = load_artifact(args.model, args.model_sha256)
        features = extract_event_features(scoped)
        feature_shift = diagnostics(features, plan, model.feature_names)
        predictions = model.predict_proba(features)
        scores = dict(zip(features.event_ids, map(float, predictions), strict=True))
        report = evaluate(data, labels, plan, scores, threshold)
        report["feature_shift"] = feature_shift
        report["input_sha256"] = {
            name: hashlib.sha256(content).hexdigest() for name, content in inputs.items()
        }
        report["model_sha256"] = args.model_sha256
        root = Path(__file__).resolve().parents[1]
        source_digest = hashlib.sha256()
        for source in sorted(root.rglob("*.py")):
            source_digest.update(source.relative_to(root).as_posix().encode() + b"\0")
            source_digest.update(hashlib.sha256(source.read_bytes()).digest())
        report["software"] = dict(
            package_version=__version__,
            python_version=platform.python_version(),
            sklearn_version=sklearn.__version__,
            numpy_version=np.__version__,
            feature_names=list(model.feature_names),
            source_tree_sha256=source_digest.hexdigest(),
        )
        report["plan"] = plan.model_dump(mode="json")
        encoded = json.dumps(report, indent=2, allow_nan=False)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded + "\n")
        print(
            json.dumps(
                {"status": "evaluated", "production_ready": False, "data_origin": plan.data_origin}
            )
        )
    except Exception as error:
        # Source paths, labels, payment fields and operator keys must not reach logs.
        code = "EVALUATION_INPUT_OR_RUNTIME_ERROR"
        for kind, value in (
            (FileExistsError, "REPORT_EXISTS"),
            (FileNotFoundError, "INPUT_NOT_FOUND"),
            (PermissionError, "FILE_ACCESS_DENIED"),
            (ValidationError, "EVALUATION_CONTRACT_INVALID"),
        ):
            if isinstance(error, kind):
                code = value
                break
        print(json.dumps({"status": "unavailable", "code": code}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
