"""Read-only evidence service over detected candidate rings."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC
from typing import Any

from ringsentinel.data.schema import DatasetBundle, EntityType, EventType, PaymentEvent
from ringsentinel.data.validation import calculate_ring_exposure
from ringsentinel.detection.candidates import RingCandidate


class RingEvidenceService:
    """Expose computed event/graph facts without consulting fraud ground truth."""

    def __init__(
        self,
        bundle: DatasetBundle,
        candidates: tuple[RingCandidate, ...],
        *,
        scores: dict[str, float] | None = None,
    ) -> None:
        self._entities = {entity.entity_id: entity for entity in bundle.entities}
        self._events = {event.event_id: event for event in bundle.events}
        self._candidates = {candidate.candidate_id: candidate for candidate in candidates}
        self._scores = dict(scores or {})

    def _candidate(self, candidate_id: str) -> RingCandidate:
        try:
            return self._candidates[candidate_id]
        except KeyError as error:
            raise KeyError(f"unknown candidate ring: {candidate_id}") from error

    def _candidate_events(self, candidate_id: str) -> tuple[PaymentEvent, ...]:
        candidate = self._candidate(candidate_id)
        return tuple(
            sorted(
                (self._events[event_id] for event_id in candidate.related_event_ids),
                key=lambda event: (event.timestamp, event.event_id),
            )
        )

    def get_candidate_ring(self, candidate_id: str) -> dict[str, Any]:
        candidate = self._candidate(candidate_id)
        return {
            "candidate_id": candidate.candidate_id,
            "risk_score": candidate.risk_score,
            "first_suspicious_timestamp": candidate.first_suspicious_timestamp.isoformat(),
            "estimated_exposure_minor": candidate.estimated_exposure_minor,
            "suspicious_relationships": list(candidate.suspicious_relationships),
            "evidence": dict(sorted(candidate.evidence.items())),
            "member_entity_ids": list(candidate.member_entity_ids),
            "related_event_ids": list(candidate.related_event_ids),
        }

    def get_ring_members(self, candidate_id: str) -> list[dict[str, Any]]:
        candidate = self._candidate(candidate_id)
        return [
            {
                "entity_id": entity_id,
                "entity_type": self._entities[entity_id].entity_type.value,
                "created_at": self._entities[entity_id].created_at.isoformat(),
            }
            for entity_id in candidate.member_entity_ids
        ]

    def _shared_customer_entities(
        self,
        candidate_id: str,
        accessor: Callable[[PaymentEvent], str],
    ) -> list[dict[str, Any]]:
        customers: defaultdict[str, set[str]] = defaultdict(set)
        event_counts: Counter[str] = Counter()
        for event in self._candidate_events(candidate_id):
            entity_id = accessor(event)
            customers[entity_id].add(event.customer_id)
            event_counts[entity_id] += 1
        return [
            {
                "entity_id": entity_id,
                "customer_ids": sorted(customer_ids),
                "customer_count": len(customer_ids),
                "event_count": event_counts[entity_id],
            }
            for entity_id, customer_ids in sorted(customers.items())
            if len(customer_ids) >= 2
        ]

    def get_shared_devices(self, candidate_id: str) -> list[dict[str, Any]]:
        return self._shared_customer_entities(candidate_id, lambda event: event.device_id)

    def get_shared_ips(self, candidate_id: str) -> list[dict[str, Any]]:
        return self._shared_customer_entities(candidate_id, lambda event: event.ip_id)

    def get_shared_cards(self, candidate_id: str) -> list[dict[str, Any]]:
        return self._shared_customer_entities(candidate_id, lambda event: event.card_id)

    def get_shared_addresses(self, candidate_id: str) -> list[dict[str, Any]]:
        return self._shared_customer_entities(candidate_id, lambda event: event.address_id)

    def get_shared_payout_accounts(self, candidate_id: str) -> list[dict[str, Any]]:
        merchants: defaultdict[str, set[str]] = defaultdict(set)
        event_counts: Counter[str] = Counter()
        for event in self._candidate_events(candidate_id):
            merchants[event.merchant_bank_account_id].add(event.merchant_id)
            event_counts[event.merchant_bank_account_id] += 1
        return [
            {
                "bank_account_id": account_id,
                "merchant_ids": sorted(merchant_ids),
                "merchant_count": len(merchant_ids),
                "event_count": event_counts[account_id],
            }
            for account_id, merchant_ids in sorted(merchants.items())
            if len(merchant_ids) >= 2
        ]

    def get_transaction_timeline(self, candidate_id: str) -> list[dict[str, Any]]:
        return [
            {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "transaction_id": event.transaction_id,
                "timestamp": event.timestamp.isoformat(),
                "amount_minor": event.amount_minor,
                "status": event.status.value,
                "customer_id": event.customer_id,
                "merchant_id": event.merchant_id,
                "risk_score": self._scores.get(event.event_id),
            }
            for event in self._candidate_events(candidate_id)
        ]

    def get_refund_patterns(self, candidate_id: str) -> dict[str, Any]:
        events = self._candidate_events(candidate_id)
        payments = {
            event.transaction_id: event
            for event in self._events.values()
            if event.event_type is EventType.PAYMENT
        }
        refunds = []
        for event in events:
            if event.event_type is not EventType.REFUND:
                continue
            original = payments.get(event.original_transaction_id or "")
            refunds.append(
                {
                    "refund_event_id": event.event_id,
                    "original_transaction_id": event.original_transaction_id,
                    "timestamp": event.timestamp.isoformat(),
                    "amount_minor": event.amount_minor,
                    "refund_fraction": (
                        event.amount_minor / original.amount_minor if original else None
                    ),
                    "delay_hours": (
                        (event.timestamp - original.timestamp).total_seconds() / 3600
                        if original
                        else None
                    ),
                }
            )
        return {
            "refund_count": len(refunds),
            "refund_amount_minor": sum(item["amount_minor"] for item in refunds),
            "refunds": refunds,
        }

    def get_merchant_relationships(self, candidate_id: str) -> list[dict[str, Any]]:
        customers: defaultdict[str, set[str]] = defaultdict(set)
        payouts: dict[str, str] = {}
        counts: Counter[str] = Counter()
        for event in self._candidate_events(candidate_id):
            customers[event.merchant_id].add(event.customer_id)
            payouts[event.merchant_id] = event.merchant_bank_account_id
            counts[event.merchant_id] += 1
        return [
            {
                "merchant_id": merchant_id,
                "payout_account_id": payouts[merchant_id],
                "customer_ids": sorted(customer_ids),
                "customer_count": len(customer_ids),
                "event_count": counts[merchant_id],
            }
            for merchant_id, customer_ids in sorted(customers.items())
        ]

    def get_temporal_activity(self, candidate_id: str) -> list[dict[str, Any]]:
        buckets: defaultdict[str, list[PaymentEvent]] = defaultdict(list)
        for event in self._candidate_events(candidate_id):
            hour = event.timestamp.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            buckets[hour.isoformat()].append(event)
        return [
            {
                "hour": hour,
                "event_count": len(events),
                "payment_count": sum(event.event_type is EventType.PAYMENT for event in events),
                "refund_count": sum(event.event_type is EventType.REFUND for event in events),
                "amount_minor": sum(event.amount_minor for event in events),
                "unique_customers": len({event.customer_id for event in events}),
            }
            for hour, events in sorted(buckets.items())
        ]

    def calculate_exposure(self, candidate_id: str) -> dict[str, Any]:
        events = self._candidate_events(candidate_id)
        event_ids = {event.event_id for event in events}
        return {
            "candidate_id": candidate_id,
            "estimated_exposure_minor": calculate_ring_exposure(
                tuple(self._events.values()), event_ids
            ),
            "definition": (
                "Captured purchase value or abusive refund value, counted once per original "
                "payment; a refund replaces rather than adds to purchase exposure."
            ),
        }

    def compare_member_behavior(self, candidate_id: str) -> list[dict[str, Any]]:
        by_customer: defaultdict[str, list[PaymentEvent]] = defaultdict(list)
        for event in self._candidate_events(candidate_id):
            by_customer[event.customer_id].append(event)
        return [
            {
                "customer_id": customer_id,
                "event_count": len(events),
                "payment_count": sum(event.event_type is EventType.PAYMENT for event in events),
                "refund_count": sum(event.event_type is EventType.REFUND for event in events),
                "total_amount_minor": sum(event.amount_minor for event in events),
                "mean_amount_minor": sum(event.amount_minor for event in events) / len(events),
                "merchant_count": len({event.merchant_id for event in events}),
                "device_count": len({event.device_id for event in events}),
                "ip_count": len({event.ip_id for event in events}),
                "first_event_at": min(event.timestamp for event in events).isoformat(),
                "last_event_at": max(event.timestamp for event in events).isoformat(),
            }
            for customer_id, events in sorted(by_customer.items())
            if self._entities[customer_id].entity_type is EntityType.CUSTOMER
        ]
