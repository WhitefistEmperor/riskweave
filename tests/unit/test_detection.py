from __future__ import annotations

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import GenerationConfig
from ringsentinel.detection.candidates import generate_ring_candidates
from ringsentinel.evaluation.metrics import evaluate_rings


def test_candidate_generation_recovers_linked_ground_truth_with_perfect_scores() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=35, transactions=500)).generate()
    labels = {label.subject_id: label.is_fraud for label in bundle.event_labels}
    scores = {event.event_id: float(labels[event.event_id]) for event in bundle.events}

    candidates = generate_ring_candidates(bundle, scores, threshold=0.5)
    evaluation = evaluate_rings(bundle, candidates, scores, threshold=0.5)

    assert candidates
    assert evaluation.true_rings_detected == len(bundle.fraud_rings)
    assert evaluation.ring_detection_rate == 1.0
    assert evaluation.benign_communities_flagged == 0
    assert all(candidate.evidence["events"] >= 2 for candidate in candidates)
    assert all(candidate.estimated_exposure_minor > 0 for candidate in candidates)
