"""Build a queryable NetworkX representation of the payment ecosystem."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import networkx as nx

from ringsentinel.data.schema import DatasetBundle, EntityType, EventType, PaymentEvent


@dataclass(slots=True)
class TemporalPaymentGraph:
    """Heterogeneous temporal graph plus focused relationship indexes."""

    graph: nx.MultiDiGraph
    event_by_id: dict[str, PaymentEvent]
    customers_by_device: dict[str, frozenset[str]]
    customers_by_card: dict[str, frozenset[str]]
    customers_by_ip: dict[str, frozenset[str]]
    customers_by_address: dict[str, frozenset[str]]
    merchants_by_payout: dict[str, frozenset[str]]
    events_by_customer: dict[str, tuple[str, ...]]
    events_by_merchant: dict[str, tuple[str, ...]]

    def related_events(self, entity_id: str) -> tuple[PaymentEvent, ...]:
        """Return an entity's events in timestamp order."""

        event_ids = self.events_by_customer.get(entity_id, ()) or self.events_by_merchant.get(
            entity_id, ()
        )
        return tuple(self.event_by_id[event_id] for event_id in event_ids)


def build_temporal_graph(
    bundle: DatasetBundle, *, until: datetime | None = None
) -> TemporalPaymentGraph:
    """Materialize entity/event nodes and timestamped relationships up to ``until``."""

    graph = nx.MultiDiGraph()
    for entity in bundle.entities:
        graph.add_node(
            entity.entity_id,
            node_type=entity.entity_type.value,
            created_at=entity.created_at,
            **entity.attributes,
        )

    customer_indexes = {
        "device": {},
        "card": {},
        "ip": {},
        "address": {},
    }
    merchant_payout: dict[str, set[str]] = {}
    customer_events: dict[str, list[str]] = {}
    merchant_events: dict[str, list[str]] = {}
    event_by_id: dict[str, PaymentEvent] = {}
    transaction_node_by_id: dict[str, str] = {}

    for event in sorted(bundle.events, key=lambda item: (item.timestamp, item.event_id)):
        if until is not None and event.timestamp > until:
            continue
        event_by_id[event.event_id] = event
        node_type = (
            EntityType.REFUND.value
            if event.event_type is EventType.REFUND
            else EntityType.TRANSACTION.value
        )
        graph.add_node(
            event.event_id,
            node_type=node_type,
            timestamp=event.timestamp,
            amount_minor=event.amount_minor,
            status=event.status.value,
        )
        relationships = (
            (event.customer_id, event.event_id, "INITIATED"),
            (event.event_id, event.card_id, "USES_CARD"),
            (event.event_id, event.device_id, "FROM_DEVICE"),
            (event.event_id, event.ip_id, "CONNECTS_FROM_IP"),
            (event.event_id, event.address_id, "LOCATED_AT_ADDRESS"),
            (event.event_id, event.merchant_id, "PAID_TO_MERCHANT"),
            (event.merchant_id, event.merchant_bank_account_id, "PAYS_OUT_TO"),
            (event.customer_id, event.card_id, "CUSTOMER_USES_CARD"),
            (event.customer_id, event.device_id, "CUSTOMER_USES_DEVICE"),
            (event.customer_id, event.ip_id, "CUSTOMER_CONNECTS_FROM_IP"),
            (event.customer_id, event.address_id, "CUSTOMER_LOCATED_AT_ADDRESS"),
            (event.customer_id, event.merchant_id, "CUSTOMER_BUYS_FROM"),
        )
        for source, target, relationship in relationships:
            graph.add_edge(
                source,
                target,
                relationship=relationship,
                event_id=event.event_id,
                timestamp=event.timestamp,
            )
        if event.event_type is EventType.PAYMENT:
            transaction_node_by_id[event.transaction_id] = event.event_id
        elif event.original_transaction_id in transaction_node_by_id:
            graph.add_edge(
                event.event_id,
                transaction_node_by_id[event.original_transaction_id],
                relationship="REFUND_OF",
                event_id=event.event_id,
                timestamp=event.timestamp,
            )

        for index_name, entity_id in (
            ("device", event.device_id),
            ("card", event.card_id),
            ("ip", event.ip_id),
            ("address", event.address_id),
        ):
            customer_indexes[index_name].setdefault(entity_id, set()).add(event.customer_id)
        merchant_payout.setdefault(event.merchant_bank_account_id, set()).add(event.merchant_id)
        customer_events.setdefault(event.customer_id, []).append(event.event_id)
        merchant_events.setdefault(event.merchant_id, []).append(event.event_id)

    def freeze(index: dict[str, set[str]]) -> dict[str, frozenset[str]]:
        return {key: frozenset(value) for key, value in index.items()}

    return TemporalPaymentGraph(
        graph=graph,
        event_by_id=event_by_id,
        customers_by_device=freeze(customer_indexes["device"]),
        customers_by_card=freeze(customer_indexes["card"]),
        customers_by_ip=freeze(customer_indexes["ip"]),
        customers_by_address=freeze(customer_indexes["address"]),
        merchants_by_payout=freeze(merchant_payout),
        events_by_customer={key: tuple(value) for key, value in customer_events.items()},
        events_by_merchant={key: tuple(value) for key, value in merchant_events.items()},
    )
