"""Leakage-safe chronological replay of precomputed causal model scores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ringsentinel.data.schema import DatasetBundle, EventType
from ringsentinel.detection.candidates import generate_ring_candidates
from ringsentinel.features.extractor import FeatureTable
from ringsentinel.models.tabular import BoostedTreeDetector


@dataclass(frozen=True, slots=True)
class ReplaySnapshot:
    timestamp: datetime
    processed_event_count: int
    suspicious_event_count: int
    candidate_count: int
    candidate_ids: tuple[str, ...]
    newly_appeared_candidate_ids: tuple[str, ...]
    top_candidate_risk_score: float | None
    top_candidate_customer_count: int | None
    top_candidate_event_count: int | None


@dataclass(frozen=True, slots=True)
class ReplayResult:
    started_at: datetime
    ended_at: datetime
    processed_event_count: int
    first_suspicious_timestamp: datetime | None
    first_candidate_timestamp: datetime | None
    snapshots: tuple[ReplaySnapshot, ...]


class ChronologicalReplay:
    """Replay events in event-time order; candidate generation sees only the current prefix."""

    def __init__(
        self,
        bundle: DatasetBundle,
        scores: dict[str, float],
        *,
        threshold: float,
    ) -> None:
        event_ids = {event.event_id for event in bundle.events}
        if set(scores) != event_ids:
            raise ValueError("scores must cover every event exactly once")
        self.bundle = bundle
        self.scores = dict(scores)
        self.threshold = threshold

    @classmethod
    def from_model(
        cls,
        bundle: DatasetBundle,
        features: FeatureTable,
        model: BoostedTreeDetector,
        *,
        threshold: float,
    ) -> ChronologicalReplay:
        scores = model.predict_proba(features)
        return cls(
            bundle,
            dict(zip(features.event_ids, scores, strict=True)),
            threshold=threshold,
        )

    def replay(self) -> ReplayResult:
        events = sorted(self.bundle.events, key=lambda event: (event.timestamp, event.event_id))
        if not events:
            raise ValueError("cannot replay an empty ecosystem")
        prefix = []
        visible_scores: dict[str, float] = {}
        snapshots: list[ReplaySnapshot] = []
        seen_candidate_ids: set[str] = set()
        suspicious_count = 0
        first_suspicious: datetime | None = None
        first_candidate: datetime | None = None

        for index, event in enumerate(events, start=1):
            prefix.append(event)
            visible_scores[event.event_id] = self.scores[event.event_id]
            suspicious = (
                self.scores[event.event_id] >= self.threshold
                and event.event_type in {EventType.PAYMENT, EventType.REFUND}
            )
            if not suspicious:
                continue
            suspicious_count += 1
            first_suspicious = first_suspicious or event.timestamp
            prefix_bundle = self.bundle.model_copy(update={"events": tuple(prefix)})
            candidates = generate_ring_candidates(
                prefix_bundle,
                visible_scores,
                threshold=self.threshold,
            )
            candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
            new_ids = tuple(item for item in candidate_ids if item not in seen_candidate_ids)
            seen_candidate_ids.update(candidate_ids)
            top = candidates[0] if candidates else None
            if top is not None and first_candidate is None:
                first_candidate = event.timestamp
            snapshots.append(
                ReplaySnapshot(
                    timestamp=event.timestamp,
                    processed_event_count=index,
                    suspicious_event_count=suspicious_count,
                    candidate_count=len(candidates),
                    candidate_ids=candidate_ids,
                    newly_appeared_candidate_ids=new_ids,
                    top_candidate_risk_score=top.risk_score if top else None,
                    top_candidate_customer_count=(
                        int(top.evidence["customers"]) if top else None
                    ),
                    top_candidate_event_count=int(top.evidence["events"]) if top else None,
                )
            )

        return ReplayResult(
            started_at=events[0].timestamp,
            ended_at=events[-1].timestamp,
            processed_event_count=len(events),
            first_suspicious_timestamp=first_suspicious,
            first_candidate_timestamp=first_candidate,
            snapshots=tuple(snapshots),
        )
