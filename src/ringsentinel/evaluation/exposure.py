"""Candidate-to-ground-truth exposure evaluation kept separate from detection metrics."""

from __future__ import annotations

from statistics import median
from typing import Any

from ringsentinel.data.schema import DatasetBundle, EntityType, FraudRingGroundTruth
from ringsentinel.detection.candidates import RingCandidate


def candidate_match_f1(
    bundle: DatasetBundle,
    ring: FraudRingGroundTruth,
    candidate: RingCandidate,
) -> float:
    """Return the customer-member F1 when at least two related events also overlap."""

    entity_types = {entity.entity_id: entity.entity_type for entity in bundle.entities}
    truth_customers = {
        item for item in ring.member_entity_ids if entity_types[item] is EntityType.CUSTOMER
    }
    candidate_customers = {
        item for item in candidate.member_entity_ids if entity_types[item] is EntityType.CUSTOMER
    }
    overlap = len(truth_customers & candidate_customers)
    event_overlap = len(set(ring.related_event_ids) & set(candidate.related_event_ids))
    if overlap < 2 or event_overlap < 2 or not candidate_customers:
        return 0.0
    precision = overlap / len(candidate_customers)
    recall = overlap / len(truth_customers)
    return 2 * precision * recall / (precision + recall)


def match_candidates_to_truth(
    bundle: DatasetBundle,
    candidates: tuple[RingCandidate, ...],
    *,
    minimum_match_f1: float = 0.25,
) -> dict[str, RingCandidate]:
    """Select the strongest deterministic candidate match for each truth ring."""

    matches: dict[str, RingCandidate] = {}
    for ring in bundle.fraud_rings:
        ranked = sorted(
            ((candidate_match_f1(bundle, ring, candidate), candidate) for candidate in candidates),
            key=lambda item: (-item[0], item[1].candidate_id),
        )
        if ranked and ranked[0][0] >= minimum_match_f1:
            matches[ring.ring_id] = ranked[0][1]
    return matches


def evaluate_exposure(
    bundle: DatasetBundle,
    candidates: tuple[RingCandidate, ...],
) -> dict[str, Any]:
    """Measure estimation error for matched rings and end-to-end with misses valued at zero."""

    matches = match_candidates_to_truth(bundle, candidates)
    rows: list[dict[str, Any]] = []
    for ring in sorted(bundle.fraud_rings, key=lambda item: item.ring_id):
        candidate = matches.get(ring.ring_id)
        estimated = candidate.estimated_exposure_minor if candidate else 0
        actual = ring.monetary_exposure_minor
        absolute_error = abs(estimated - actual)
        rows.append(
            {
                "ring_id": ring.ring_id,
                "archetype": ring.archetype.value,
                "detected": candidate is not None,
                "candidate_id": candidate.candidate_id if candidate else None,
                "actual_exposure_minor": actual,
                "estimated_exposure_minor": estimated,
                "absolute_error_minor": absolute_error,
                "relative_error": absolute_error / actual if actual else None,
            }
        )

    matched = [row for row in rows if row["detected"]]

    def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
        errors = [int(row["absolute_error_minor"]) for row in records]
        relative = [
            float(row["relative_error"]) for row in records if row["relative_error"] is not None
        ]
        return {
            "ring_count": len(records),
            "mae_minor": sum(errors) / len(errors) if errors else None,
            "median_absolute_error_minor": median(errors) if errors else None,
            "mean_relative_error": sum(relative) / len(relative) if relative else None,
            "aggregate_estimated_exposure_minor": sum(
                int(row["estimated_exposure_minor"]) for row in records
            ),
            "aggregate_actual_exposure_minor": sum(
                int(row["actual_exposure_minor"]) for row in records
            ),
        }

    return {
        "definition": (
            "At-risk value counted once per original payment: abusive refund value replaces, "
            "rather than adds to, the corresponding purchase value."
        ),
        "detection_recall": len(matched) / len(rows) if rows else 0.0,
        "matched_rings": summarize(matched),
        "end_to_end_including_missed_as_zero": summarize(rows),
        "rings": rows,
    }
