"""Adapter around the unchanged Phase 3 detector and authoritative evidence queries."""

from typing import Protocol

from ringsentinel.api.runtime import DemoRuntime
from ringsentinel.data.schema import DatasetBundle
from ringsentinel.detection.candidates import generate_ring_candidates
from ringsentinel.features.extractor import extract_event_features
from ringsentinel.investigation.evidence import RingEvidenceService

EVIDENCE_QUERIES = (
    "get_candidate_ring",
    "get_ring_members",
    "get_shared_devices",
    "get_shared_ips",
    "get_shared_cards",
    "get_shared_addresses",
    "get_shared_payout_accounts",
    "get_transaction_timeline",
    "get_refund_patterns",
    "get_merchant_relationships",
    "get_temporal_activity",
    "calculate_exposure",
    "compare_member_behavior",
)


class AnalysisEngine(Protocol):
    def analyze(self, bundle: DatasetBundle) -> dict: ...


class Phase3AnalysisEngine:
    """Same seed-105 fold model, features, threshold selection, and candidate algorithm.

    Uploaded labels never participate in fitting, threshold selection or evidence.
    This is a synthetic-trained detector, NOT a calibrated real-payment risk model.
    """

    def analyze(self, bundle: DatasetBundle) -> dict:
        runtime = DemoRuntime()
        model, threshold = runtime.model_and_threshold
        features = extract_event_features(bundle)
        scores = dict(
            zip(features.event_ids, map(float, model.predict_proba(features)), strict=True)
        )
        candidates = generate_ring_candidates(bundle, scores, threshold=threshold)
        evidence = RingEvidenceService(bundle, candidates, scores=scores)
        return {
            "schema_version": "1",
            "threshold": threshold,
            "event_count": len(bundle.events),
            "entity_count": len(bundle.entities),
            "model_scope": "synthetic-trained; uncalibrated; analyst review required",
            "rings": [
                {
                    "candidate": evidence.get_candidate_ring(candidate.candidate_id),
                    "queries": {
                        query: getattr(evidence, query)(candidate.candidate_id)
                        for query in EVIDENCE_QUERIES
                    },
                }
                for candidate in candidates
            ],
        }


class PersistedEvidence:
    """Investigator query facade over already-computed immutable run evidence."""

    def __init__(self, result: dict):
        self.rings = {
            ring["candidate"]["candidate_id"]: ring["queries"] for ring in result["rings"]
        }

    def __getattr__(self, query: str):
        if query not in EVIDENCE_QUERIES:
            raise AttributeError(query)
        return lambda candidate_id: self.rings[candidate_id][query]
