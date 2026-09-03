"""Measured event, scenario, hard-negative, and ring-level metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from ringsentinel.data.schema import DatasetBundle, EntityType
from ringsentinel.detection.candidates import RingCandidate


def labels_for_events(bundle: DatasetBundle, event_ids: tuple[str, ...]) -> np.ndarray:
    labels = {label.subject_id: label.is_fraud for label in bundle.event_labels}
    return np.asarray([labels[event_id] for event_id in event_ids], dtype=int)


def select_f1_threshold(labels: np.ndarray, scores: np.ndarray) -> float:
    """Select a threshold on validation data only using a fixed public grid."""

    best = (float("-inf"), float("-inf"), float("-inf"), 0.50)
    for threshold in np.linspace(0.05, 0.95, 91):
        predictions = scores >= threshold
        f1 = f1_score(labels, predictions, zero_division=0)
        precision = precision_score(labels, predictions, zero_division=0)
        candidate = (f1, precision, threshold, threshold)
        if candidate > best:
            best = candidate
    return best[-1]


def evaluate_events(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float]:
    predictions = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "precision": precision_score(labels, predictions, zero_division=0),
        "recall": recall_score(labels, predictions, zero_division=0),
        "f1": f1_score(labels, predictions, zero_division=0),
        "pr_auc": average_precision_score(labels, scores),
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "true_positives": float(tp),
        "false_positives": float(fp),
        "false_negatives": float(fn),
        "true_negatives": float(tn),
    }


@dataclass(frozen=True, slots=True)
class RingEvaluation:
    true_rings_detected: int
    ring_detection_rate: float
    exposure_weighted_recall: float
    mean_early_warning_delay_hours: float | None
    benign_communities_flagged: int
    scenario_results: tuple[dict[str, float | str | bool | None], ...]
    benign_results: tuple[dict[str, str | bool | int], ...]


def evaluate_rings(
    bundle: DatasetBundle,
    candidates: tuple[RingCandidate, ...],
    scores: dict[str, float],
    threshold: float,
) -> RingEvaluation:
    """Match candidates to ground truth only after detection is complete."""

    entity_type = {entity.entity_id: entity.entity_type for entity in bundle.entities}
    event_by_id = {event.event_id: event for event in bundle.events}
    total_exposure = sum(ring.monetary_exposure_minor for ring in bundle.fraud_rings)
    detected_exposure = 0
    detected_count = 0
    delays = []
    scenario_results = []

    for ring in bundle.fraud_rings:
        truth_customers = {
            item for item in ring.member_entity_ids if entity_type[item] is EntityType.CUSTOMER
        }
        best_match = 0.0
        best_candidate: RingCandidate | None = None
        for candidate in candidates:
            candidate_customers = {
                item
                for item in candidate.member_entity_ids
                if entity_type[item] is EntityType.CUSTOMER
            }
            overlap = len(truth_customers & candidate_customers)
            if overlap < 2:
                continue
            precision = overlap / len(candidate_customers)
            recall = overlap / len(truth_customers)
            match_f1 = 2 * precision * recall / (precision + recall)
            event_overlap = len(set(ring.related_event_ids) & set(candidate.related_event_ids))
            if event_overlap >= 2 and match_f1 > best_match:
                best_match = match_f1
                best_candidate = candidate
        detected = best_candidate is not None and best_match >= 0.25
        delay: float | None = None
        if detected:
            detected_count += 1
            detected_exposure += ring.monetary_exposure_minor
            flagged_times = [
                event_by_id[event_id].timestamp
                for event_id in ring.related_event_ids
                if scores.get(event_id, 0.0) >= threshold
            ]
            if flagged_times:
                delay = (min(flagged_times) - ring.attack_start_time).total_seconds() / 3600
                delays.append(delay)
        fraud_scores = [scores.get(event_id, 0.0) for event_id in ring.fraudulent_event_ids]
        scenario_results.append(
            {
                "ring_id": ring.ring_id,
                "archetype": ring.archetype.value,
                "detected": detected,
                "match_f1": best_match,
                "fraud_event_recall": sum(score >= threshold for score in fraud_scores)
                / len(fraud_scores),
                "early_warning_delay_hours": delay,
            }
        )

    benign_results = []
    for community in bundle.benign_communities:
        truth = set(community.member_customer_ids)
        minimum_overlap = max(3, math.ceil(len(truth) * 0.25))
        max_overlap = max(
            (len(truth & set(candidate.member_entity_ids)) for candidate in candidates),
            default=0,
        )
        benign_results.append(
            {
                "community_id": community.community_id,
                "archetype": community.archetype,
                "size": len(truth),
                "flagged": max_overlap >= minimum_overlap,
                "maximum_candidate_overlap": max_overlap,
            }
        )

    return RingEvaluation(
        true_rings_detected=detected_count,
        ring_detection_rate=detected_count / len(bundle.fraud_rings),
        exposure_weighted_recall=detected_exposure / total_exposure if total_exposure else 0.0,
        mean_early_warning_delay_hours=sum(delays) / len(delays) if delays else None,
        benign_communities_flagged=sum(bool(item["flagged"]) for item in benign_results),
        scenario_results=tuple(scenario_results),
        benign_results=tuple(benign_results),
    )
