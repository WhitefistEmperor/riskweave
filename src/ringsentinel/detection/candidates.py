"""Group linked suspicious events into explainable candidate rings."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

import networkx as nx

from ringsentinel.data.schema import DatasetBundle, EntityType, EventType, PaymentEvent
from ringsentinel.data.validation import calculate_ring_exposure


@dataclass(frozen=True, slots=True)
class RingCandidate:
    candidate_id: str
    member_entity_ids: tuple[str, ...]
    related_event_ids: tuple[str, ...]
    risk_score: float
    first_suspicious_timestamp: datetime
    estimated_exposure_minor: int
    suspicious_relationships: tuple[str, ...]
    evidence: dict[str, float | int]


def _event_entities(event: PaymentEvent) -> tuple[str, ...]:
    return (
        event.customer_id,
        event.card_id,
        event.device_id,
        event.ip_id,
        event.address_id,
        event.merchant_id,
        event.merchant_bank_account_id,
    )


def generate_ring_candidates(
    bundle: DatasetBundle,
    scores: dict[str, float],
    *,
    threshold: float,
    minimum_events: int = 2,
) -> tuple[RingCandidate, ...]:
    """Create connected components from thresholded events and shared entities."""

    event_by_id = {event.event_id: event for event in bundle.events}
    suspicious = [
        event
        for event in bundle.events
        if scores.get(event.event_id, 0.0) >= threshold
        and event.event_type in {EventType.PAYMENT, EventType.REFUND}
    ]
    graph = nx.Graph()
    events_by_entity: defaultdict[str, set[str]] = defaultdict(set)
    for event in suspicious:
        entities = _event_entities(event)
        for entity_id in entities:
            events_by_entity[entity_id].add(event.event_id)
        for target in entities[1:5]:
            graph.add_edge(event.customer_id, target)
        graph.add_edge(event.customer_id, event.merchant_id)
        graph.add_edge(event.merchant_id, event.merchant_bank_account_id)

    entity_type = {entity.entity_id: entity.entity_type for entity in bundle.entities}
    candidates: list[RingCandidate] = []
    for component in nx.connected_components(graph):
        event_ids = sorted(
            {event_id for entity_id in component for event_id in events_by_entity[entity_id]}
        )
        customer_count = sum(entity_type[item] is EntityType.CUSTOMER for item in component)
        if len(event_ids) < minimum_events or customer_count < 2:
            continue
        component_events = [event_by_id[event_id] for event_id in event_ids]
        component_scores = sorted((scores[event_id] for event_id in event_ids), reverse=True)
        top_count = max(1, min(5, len(component_scores)))
        risk_score = sum(component_scores[:top_count]) / top_count
        exposure = calculate_ring_exposure(bundle.events, set(event_ids))

        device_customers: defaultdict[str, set[str]] = defaultdict(set)
        ip_customers: defaultdict[str, set[str]] = defaultdict(set)
        address_customers: defaultdict[str, set[str]] = defaultdict(set)
        payout_merchants: defaultdict[str, set[str]] = defaultdict(set)
        event_types = Counter()
        for event in component_events:
            device_customers[event.device_id].add(event.customer_id)
            ip_customers[event.ip_id].add(event.customer_id)
            address_customers[event.address_id].add(event.customer_id)
            payout_merchants[event.merchant_bank_account_id].add(event.merchant_id)
            event_types[event.event_type.value] += 1

        evidence = {
            "member_entities": len(component),
            "customers": customer_count,
            "events": len(event_ids),
            "max_customers_per_device": max(map(len, device_customers.values())),
            "max_customers_per_ip": max(map(len, ip_customers.values())),
            "max_customers_per_address": max(map(len, address_customers.values())),
            "max_merchants_per_payout": max(map(len, payout_merchants.values())),
            "refund_events": event_types[EventType.REFUND.value],
        }
        relationships = tuple(
            name
            for name, present in (
                ("shared_device", evidence["max_customers_per_device"] > 1),
                ("shared_ip", evidence["max_customers_per_ip"] > 1),
                ("shared_address", evidence["max_customers_per_address"] > 1),
                ("shared_payout", evidence["max_merchants_per_payout"] > 1),
                ("coordinated_refunds", evidence["refund_events"] > 1),
            )
            if present
        )
        digest = hashlib.sha256("|".join(sorted(component)).encode()).hexdigest()[:12]
        candidates.append(
            RingCandidate(
                candidate_id=f"candidate_{digest}",
                member_entity_ids=tuple(sorted(component)),
                related_event_ids=tuple(event_ids),
                risk_score=risk_score,
                first_suspicious_timestamp=min(event.timestamp for event in component_events),
                estimated_exposure_minor=exposure,
                suspicious_relationships=relationships,
                evidence=evidence,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (-item.risk_score, item.candidate_id)))
