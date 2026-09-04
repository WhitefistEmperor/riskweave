"""Lazy, deterministic demo runtime backed directly by the RingSentinel package."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from functools import cached_property, lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from ringsentinel.baselines.graph_heuristic import GraphHeuristicBaseline
from ringsentinel.data.schema import DatasetBundle, EntityType
from ringsentinel.detection.candidates import RingCandidate, generate_ring_candidates
from ringsentinel.evaluation.exposure import match_candidates_to_truth
from ringsentinel.evaluation.metrics import select_f1_threshold
from ringsentinel.experiments.run import PreparedDataset, _prepare
from ringsentinel.features.extractor import NETWORK_FEATURES, TRANSACTION_FEATURES
from ringsentinel.investigation.evidence import RingEvidenceService
from ringsentinel.models.tabular import BoostedTreeDetector

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PHASE3_RESULT_PATH = PROJECT_ROOT / "results" / "phase3" / "phase3_results.json"
if not PHASE3_RESULT_PATH.exists():
    PHASE3_RESULT_PATH = Path(__file__).resolve().parents[1] / "resources" / "phase3_results.json"
DEMO_SEEDS = (101, 102, 103, 104, 105)
DEMO_TEST_SEED = 105


class DemoRuntime:
    """Build the exact seed-105 held-out fold used in the Phase 3 demo."""

    def __init__(
        self,
        *,
        seeds: tuple[int, ...] = DEMO_SEEDS,
        transactions: int = 5_000,
        result_path: Path = PHASE3_RESULT_PATH,
    ) -> None:
        self.seeds = seeds
        self.transactions = transactions
        self.result_path = result_path
        self._dataset_lock = Lock()
        self._prepared: tuple[PreparedDataset, ...] | None = None

    @cached_property
    def phase3(self) -> dict[str, Any]:
        return json.loads(self.result_path.read_text(encoding="utf-8"))

    @cached_property
    def datasets(self) -> tuple[PreparedDataset, ...]:
        # cached_property alone is not synchronized on Python 3.12+.
        with self._dataset_lock:
            if self._prepared is None:
                self._prepared = tuple(_prepare(seed, self.transactions) for seed in self.seeds)
            return self._prepared

    @cached_property
    def test_dataset(self) -> PreparedDataset:
        return next(dataset for dataset in self.datasets if dataset.seed == DEMO_TEST_SEED)

    @cached_property
    def model_and_threshold(self) -> tuple[BoostedTreeDetector, float]:
        test_index = next(
            index for index, dataset in enumerate(self.datasets) if dataset.seed == DEMO_TEST_SEED
        )
        validation = self.datasets[(test_index + 1) % len(self.datasets)]
        training = tuple(
            dataset
            for index, dataset in enumerate(self.datasets)
            if index not in {test_index, (test_index + 1) % len(self.datasets)}
        )
        model = BoostedTreeDetector(
            TRANSACTION_FEATURES + NETWORK_FEATURES,
            random_state=self.test_dataset.seed,
        )
        model.fit(
            tuple(dataset.features for dataset in training),
            tuple(dataset.labels for dataset in training),
        )
        threshold = select_f1_threshold(
            validation.labels,
            model.predict_proba(validation.features),
        )
        return model, float(threshold)

    @cached_property
    def scores(self) -> dict[str, float]:
        model, _ = self.model_and_threshold
        values = model.predict_proba(self.test_dataset.features)
        return dict(zip(self.test_dataset.features.event_ids, map(float, values), strict=True))

    @cached_property
    def candidates(self) -> tuple[RingCandidate, ...]:
        _, threshold = self.model_and_threshold
        return generate_ring_candidates(
            self.test_dataset.bundle,
            self.scores,
            threshold=threshold,
        )

    @cached_property
    def evidence(self) -> RingEvidenceService:
        return RingEvidenceService(
            self.test_dataset.bundle,
            self.candidates,
            scores=self.scores,
        )

    @cached_property
    def truth_by_candidate(self) -> dict[str, Any]:
        matches = match_candidates_to_truth(self.test_dataset.bundle, self.candidates)
        return {candidate.candidate_id: ring_id for ring_id, candidate in matches.items()}

    @property
    def bundle(self) -> DatasetBundle:
        return self.test_dataset.bundle

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "ringsentinel-api",
            "phase": 4,
            "demo_seed": DEMO_TEST_SEED,
        }

    def overview(self) -> dict[str, Any]:
        suspicious_entities = {
            entity_id for candidate in self.candidates for entity_id in candidate.member_entity_ids
        }
        stream = self.phase3["streaming_demo"]
        return {
            "demo_seed": DEMO_TEST_SEED,
            "monitored_entities": len(self.bundle.entities),
            "monitored_events": len(self.bundle.events),
            "candidate_rings": len(self.candidates),
            "suspicious_entities": len(suspicious_entities),
            "estimated_exposure_minor": sum(
                candidate.estimated_exposure_minor for candidate in self.candidates
            ),
            "simulator_start_timestamp": stream["started_at"],
            "attack_start_timestamp": stream["evaluation_overlay"]["attack_start_time"],
            "candidate_detection_timestamp": stream["evaluation_overlay"][
                "candidate_detected_time"
            ],
            "detection_delay_minutes": stream["evaluation_overlay"][
                "candidate_detection_delay_minutes"
            ],
            "synthetic_benchmark": True,
        }

    def benchmark(self) -> dict[str, Any]:
        aggregate = self.phase3["updated_benchmark"]["aggregate"]
        selected_models = {
            name: aggregate[name]
            for name in ("transaction_hgb", "graph_heuristic", "network_aware_hgb")
        }
        ablation_names = (
            "transaction_only",
            "transaction_plus_infrastructure",
            "transaction_plus_temporal",
            "transaction_plus_structural",
            "full_network_aware",
        )
        return {
            "synthetic_benchmark": True,
            "seeds": self.phase3["seeds"],
            "transactions_per_seed": self.phase3["transactions_per_seed"],
            "models": selected_models,
            "ablations": {
                name: self.phase3["ablations"]["aggregate"][name] for name in ablation_names
            },
            "exposure": {
                key: value for key, value in self.phase3["exposure"].items() if key != "rings"
            },
            "limitations": [
                "Validated on synthetic ecosystems; not a production fraud-rate claim.",
                "Real-world distribution shift is unknown.",
                "Merchant-collusion generalization varied across seeds.",
                "Model probabilities are not production calibrated.",
                "Production use requires retraining and ongoing monitoring.",
            ],
        }

    def _ring_for_candidate(self, candidate_id: str) -> Any | None:
        ring_id = self.truth_by_candidate.get(candidate_id)
        return next(
            (ring for ring in self.bundle.fraud_rings if ring.ring_id == ring_id),
            None,
        )

    def list_candidates(self) -> list[dict[str, Any]]:
        return [self.candidate(candidate.candidate_id) for candidate in self.candidates]

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        payload = self.evidence.get_candidate_ring(candidate_id)
        ring = self._ring_for_candidate(candidate_id)
        appeared_at = self._first_connected_precursor(candidate_id)
        payload["first_connected_precursor_timestamp"] = appeared_at.isoformat()
        payload["ground_truth_overlay"] = (
            {
                "demo_only": True,
                "ring_id": ring.ring_id,
                "archetype": ring.archetype.value,
                "attack_start_time": ring.attack_start_time.isoformat(),
                "detection_delay_hours": (
                    (appeared_at - ring.attack_start_time).total_seconds() / 3600
                ),
            }
            if ring
            else None
        )
        return payload

    def _first_connected_precursor(self, candidate_id: str) -> datetime:
        """Earliest qualifying component in this candidate's observed event lineage."""
        candidate = next(item for item in self.candidates if item.candidate_id == candidate_id)
        event_ids = set(candidate.related_event_ids)
        ordered = sorted(
            (event for event in self.bundle.events if event.event_id in event_ids),
            key=lambda event: (event.timestamp, event.event_id),
        )
        for index, event in enumerate(ordered, start=1):
            prefix = self.bundle.model_copy(update={"events": tuple(ordered[:index])})
            if generate_ring_candidates(prefix, self.scores, threshold=self.model_and_threshold[1]):
                return event.timestamp
        raise ValueError("candidate has no qualifying precursor")

    def snapshot_view(self, event_count: int | None = None) -> DemoRuntime:
        """Read-only prefix view sharing the frozen trained model, never future events."""
        if event_count is None:
            return self
        ordered = sorted(self.bundle.events, key=lambda event: (event.timestamp, event.event_id))
        if not 1 <= event_count <= len(ordered):
            raise ValueError("event_count outside ecosystem bounds")
        prefix = tuple(ordered[:event_count])
        view = DemoRuntime(
            seeds=self.seeds, transactions=self.transactions, result_path=self.result_path
        )
        view.__dict__["test_dataset"] = replace(
            self.test_dataset, bundle=self.bundle.model_copy(update={"events": prefix})
        )
        view.__dict__["model_and_threshold"] = self.model_and_threshold
        view.__dict__["scores"] = {event.event_id: self.scores[event.event_id] for event in prefix}
        return view

    def snapshot(self, event_count: int | None, candidate_id: str | None) -> dict[str, Any]:
        view = self.snapshot_view(event_count)
        candidates = view.list_candidates()
        selected = candidate_id or (candidates[0]["candidate_id"] if candidates else None)
        payload: dict[str, Any] = {
            "scope": "observed_prefix" if event_count is not None else "completed_ecosystem",
            "observed_event_count": len(view.bundle.events),
            "as_of": max(event.timestamp for event in view.bundle.events).isoformat(),
            "candidates": candidates,
            "selected": None,
        }
        if selected:
            payload["selected"] = {
                "candidate": view.candidate(selected),
                "members": view.evidence.get_ring_members(selected),
                "graph": view.candidate_graph(selected),
                "timeline": view.candidate_timeline(selected),
                "evidence": view.candidate_evidence(selected),
            }
        return payload

    def candidate_evidence(self, candidate_id: str) -> dict[str, Any]:
        return {
            "candidate": self.evidence.get_candidate_ring(candidate_id),
            "shared_devices": self.evidence.get_shared_devices(candidate_id),
            "shared_ips": self.evidence.get_shared_ips(candidate_id),
            "shared_cards": self.evidence.get_shared_cards(candidate_id),
            "shared_addresses": self.evidence.get_shared_addresses(candidate_id),
            "shared_payout_accounts": self.evidence.get_shared_payout_accounts(candidate_id),
            "refund_patterns": self.evidence.get_refund_patterns(candidate_id),
            "merchant_relationships": self.evidence.get_merchant_relationships(candidate_id),
            "temporal_activity": self.evidence.get_temporal_activity(candidate_id),
            "exposure": self.evidence.calculate_exposure(candidate_id),
            "member_behavior": self.evidence.compare_member_behavior(candidate_id),
        }

    def candidate_graph(self, candidate_id: str) -> dict[str, Any]:
        candidate = next(item for item in self.candidates if item.candidate_id == candidate_id)
        shared_ids = {
            item["entity_id"]
            for query in (
                self.evidence.get_shared_devices,
                self.evidence.get_shared_ips,
                self.evidence.get_shared_cards,
                self.evidence.get_shared_addresses,
            )
            for item in query(candidate_id)
        }
        shared_ids.update(
            item["bank_account_id"]
            for item in self.evidence.get_shared_payout_accounts(candidate_id)
        )
        nodes = [
            {
                "id": entity_id,
                "type": self._entity_type(entity_id).value,
                "shared_infrastructure": entity_id in shared_ids,
            }
            for entity_id in candidate.member_entity_ids
        ]
        edges: Counter[tuple[str, str, str]] = Counter()
        event_by_id = {event.event_id: event for event in self.bundle.events}
        for event_id in candidate.related_event_ids:
            event = event_by_id[event_id]
            relationships = (
                (event.customer_id, event.device_id, "USES_DEVICE"),
                (event.customer_id, event.ip_id, "CONNECTS_FROM_IP"),
                (event.customer_id, event.card_id, "USES_CARD"),
                (event.customer_id, event.address_id, "LOCATED_AT"),
                (event.customer_id, event.merchant_id, "BUYS_FROM"),
                (event.merchant_id, event.merchant_bank_account_id, "PAYS_OUT_TO"),
            )
            edges.update(relationships)
        return {
            "candidate_id": candidate_id,
            "nodes": nodes,
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "relationship": relationship,
                    "event_count": count,
                    "suspicious": source in shared_ids or target in shared_ids,
                }
                for (source, target, relationship), count in sorted(edges.items())
            ],
        }

    def _entity_type(self, entity_id: str) -> EntityType:
        return next(
            entity.entity_type for entity in self.bundle.entities if entity.entity_id == entity_id
        )

    def candidate_timeline(self, candidate_id: str) -> dict[str, Any]:
        ring = self._ring_for_candidate(candidate_id)
        timeline = self.evidence.get_transaction_timeline(candidate_id)
        events: list[dict[str, Any]] = [
            {
                "timestamp": item["timestamp"],
                "kind": "refund" if item["event_type"] == "REFUND" else "payment",
                "title": f"{item['event_type'].title()} · {item['customer_id'][-6:]}",
                "detail": f"{item['amount_minor']} minor units at {item['merchant_id'][-6:]}",
                "risk_score": item["risk_score"],
                "event_id": item["event_id"],
                "ground_truth_only": False,
            }
            for item in timeline
        ]
        if ring:
            events.extend(
                {
                    "timestamp": stage.starts_at.isoformat(),
                    "kind": "attack_stage",
                    "title": stage.name.replace("_", " ").title(),
                    "detail": stage.description,
                    "risk_score": None,
                    "event_id": None,
                    "ground_truth_only": True,
                }
                for stage in ring.attack_progression
                if stage.starts_at <= max(event.timestamp for event in self.bundle.events)
            )
        events.append(
            {
                "timestamp": self._first_connected_precursor(candidate_id).isoformat(),
                "kind": "candidate_created",
                "title": "First connected candidate precursor",
                "detail": "At least two linked above-threshold events from two customers. "
                "Membership may grow or merge later; this is not the final ring's creation time.",
                "risk_score": None,
                "event_id": None,
                "ground_truth_only": False,
            }
        )
        return {
            "candidate_id": candidate_id,
            "events": sorted(events, key=lambda item: (item["timestamp"], item["kind"])),
        }

    def simulation(self) -> dict[str, Any]:
        stream = self.phase3["streaming_demo"]
        overlay = stream["evaluation_overlay"]
        attack_start = datetime.fromisoformat(overlay["attack_start_time"])
        detection_time = datetime.fromisoformat(overlay["candidate_detected_time"])
        ordered = sorted(self.bundle.events, key=lambda event: (event.timestamp, event.event_id))
        focus_ring = min(
            self.bundle.fraud_rings,
            key=lambda ring: (ring.attack_start_time, ring.ring_id),
        )
        focus_ids = set(focus_ring.related_event_ids)
        fraud_ids = set(focus_ring.fraudulent_event_ids)
        first_focus_index = next(
            index for index, event in enumerate(ordered) if event.event_id in focus_ids
        )
        start_index = max(0, first_focus_index - 80)
        end_time = detection_time + timedelta(hours=1)
        window = [event for event in ordered[start_index:] if event.timestamp <= end_time]
        label_by_event = {label.subject_id: label for label in self.bundle.event_labels}
        accumulated_customers: set[str] = set()
        accumulated_devices: set[str] = set()
        accumulated_ips: set[str] = set()
        ordered_index = {event.event_id: index for index, event in enumerate(ordered)}
        events = []
        for event in window:
            is_focus = event.event_id in focus_ids
            if is_focus:
                accumulated_customers.add(event.customer_id)
                accumulated_devices.add(event.device_id)
                accumulated_ips.add(event.ip_id)
            prefix_events = tuple(ordered[: ordered_index[event.event_id] + 1])
            prefix_bundle = self.bundle.model_copy(update={"events": prefix_events})
            prefix_scores = {item.event_id: self.scores[item.event_id] for item in prefix_events}
            prefix_candidates = generate_ring_candidates(
                prefix_bundle, prefix_scores, threshold=self.model_and_threshold[1]
            )
            live_candidate = match_candidates_to_truth(
                self.bundle.model_copy(update={"fraud_rings": (focus_ring,)}),
                prefix_candidates,
            ).get(focus_ring.ring_id)
            events.append(
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type.value,
                    "amount_minor": event.amount_minor,
                    "customer_id": event.customer_id,
                    "merchant_id": event.merchant_id,
                    "device_id": event.device_id,
                    "ip_id": event.ip_id,
                    "risk_score": self.scores[event.event_id],
                    "threshold_crossed": self.scores[event.event_id] >= self.model_and_threshold[1],
                    "observed_event_count": ordered_index[event.event_id] + 1,
                    "candidate_state": (
                        {
                            "candidate_id": live_candidate.candidate_id,
                            "risk_score": live_candidate.risk_score,
                            "customers": live_candidate.evidence["customers"],
                            "events": live_candidate.evidence["events"],
                            "estimated_exposure_minor": live_candidate.estimated_exposure_minor,
                        }
                        if live_candidate
                        else None
                    ),
                    "demo_truth": {
                        "focus_ring_event": is_focus,
                        "fraud_labeled": event.event_id in fraud_ids,
                        "attack_stage": label_by_event[event.event_id].attack_stage,
                    },
                    "accumulated_relationships": {
                        "customers": len(accumulated_customers),
                        "devices": len(accumulated_devices),
                        "ips": len(accumulated_ips),
                    },
                }
            )
        matched = match_candidates_to_truth(self.bundle, self.candidates)
        focus_candidate = matched[focus_ring.ring_id]
        return {
            "demo_seed": DEMO_TEST_SEED,
            "threshold": self.model_and_threshold[1],
            "ecosystem_event_count": len(self.bundle.events),
            "window_start_index": start_index,
            "attack_start_timestamp": attack_start.isoformat(),
            "first_alert_timestamp": detection_time.isoformat(),
            "earlier_isolated_alert_timestamp": datetime.fromisoformat(
                stream["first_suspicious_timestamp"]
            ).isoformat(),
            "detection_delay_minutes": overlay["candidate_detection_delay_minutes"],
            "candidate_id": focus_candidate.candidate_id,
            "events": events,
        }

    def hard_negatives(self) -> list[dict[str, Any]]:
        graph_fold = next(
            fold
            for fold in self.phase3["updated_benchmark"]["folds"]
            if fold["model"] == "graph_heuristic" and fold["test_seed"] == DEMO_TEST_SEED
        )
        network_fold = next(
            fold
            for fold in self.phase3["updated_benchmark"]["folds"]
            if fold["model"] == "network_aware_hgb" and fold["test_seed"] == DEMO_TEST_SEED
        )
        graph_results = {item["community_id"]: item for item in graph_fold["benign_results"]}
        network_results = {item["community_id"]: item for item in network_fold["benign_results"]}
        graph_scores = GraphHeuristicBaseline().predict_proba(self.test_dataset.features)
        graph_score_by_id = dict(
            zip(self.test_dataset.features.event_ids, graph_scores, strict=True)
        )
        entity_by_id = {entity.entity_id: entity for entity in self.bundle.entities}
        output = []
        for community in self.bundle.benign_communities:
            shared_types = Counter(
                entity_by_id[entity_id].entity_type.value
                for entity_id in community.shared_entity_ids
            )
            member_ids = set(community.member_customer_ids)
            community_events = [
                event for event in self.bundle.events if event.customer_id in member_ids
            ]
            shared_ids = set(community.shared_entity_ids)
            shared_edges: Counter[tuple[str, str, str]] = Counter()
            for event in community_events:
                for target, relation in (
                    (event.device_id, "USES_DEVICE"),
                    (event.ip_id, "CONNECTS_FROM_IP"),
                    (event.card_id, "USES_CARD"),
                    (event.address_id, "LOCATED_AT"),
                    (event.merchant_id, "BUYS_FROM"),
                ):
                    if target in shared_ids:
                        shared_edges[(event.customer_id, target, relation)] += 1
            output.append(
                {
                    "community_id": community.community_id,
                    "archetype": community.archetype,
                    "size": len(member_ids),
                    "rationale": community.rationale,
                    "shared_entity_types": dict(sorted(shared_types.items())),
                    "event_count": len(community_events),
                    "max_graph_heuristic_score": max(
                        (graph_score_by_id[event.event_id] for event in community_events),
                        default=0.0,
                    ),
                    "max_network_score": max(
                        (self.scores[event.event_id] for event in community_events),
                        default=0.0,
                    ),
                    "graph_heuristic_flagged": graph_results[community.community_id]["flagged"],
                    "network_aware_flagged": network_results[community.community_id]["flagged"],
                    "member_customer_ids": list(community.member_customer_ids),
                    "shared_entity_ids": list(community.shared_entity_ids),
                    "graph_threshold": float(graph_fold["threshold"]),
                    "network_threshold": self.model_and_threshold[1],
                    "graph": {
                        "nodes": [
                            {
                                "id": entity_id,
                                "type": entity_by_id[entity_id].entity_type.value,
                                "shared_infrastructure": entity_id in shared_ids,
                            }
                            for entity_id in sorted(member_ids | shared_ids)
                        ],
                        "edges": [
                            {
                                "source": source,
                                "target": target,
                                "relationship": relation,
                                "event_count": count,
                                "suspicious": False,
                            }
                            for (source, target, relation), count in sorted(shared_edges.items())
                        ],
                    },
                }
            )
        return output


@lru_cache(maxsize=1)
def get_demo_runtime() -> DemoRuntime:
    """Return the process-wide deterministic demo runtime."""

    return DemoRuntime()
