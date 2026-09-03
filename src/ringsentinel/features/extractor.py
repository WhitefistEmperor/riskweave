"""Leakage-safe causal features computed in event-time order."""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import networkx as nx
import numpy as np

from ringsentinel.data.schema import DatasetBundle, EntityType, EventType, PaymentStatus

TRANSACTION_FEATURES = (
    "amount_log",
    "account_age_days",
    "is_refund",
    "is_failed",
    "hour_sin",
    "hour_cos",
    "customer_events_1h",
    "customer_events_24h",
    "customer_amount_24h_log",
    "customer_refund_ratio_24h",
    "retry_count",
)

INFRASTRUCTURE_SHARING_FEATURES = (
    "shared_device_customers",
    "shared_ip_customers",
    "shared_card_customers",
    "shared_address_customers",
    "payout_merchants",
    "infrastructure_customer_max",
    "shared_infrastructure_concentration",
)

STRUCTURAL_GRAPH_FEATURES = (
    "merchant_customer_degree",
    "customer_merchant_degree",
    "shared_neighbor_count",
    "multi_shared_neighbor_count",
    "customer_component_size",
    "customer_local_density",
    "customer_merchant_concentration",
)

TEMPORAL_NETWORK_FEATURES = (
    "device_events_15m",
    "ip_events_15m",
    "merchant_events_15m",
    "synchronized_activity_15m",
    "infrastructure_events_24h",
    "device_refund_ratio_24h",
    "merchant_refund_ratio_24h",
    "repeated_device_ip_events",
)

NETWORK_FEATURES = (
    INFRASTRUCTURE_SHARING_FEATURES
    + STRUCTURAL_GRAPH_FEATURES
    + TEMPORAL_NETWORK_FEATURES
)


@dataclass(frozen=True, slots=True)
class EventFeatureRow:
    event_id: str
    timestamp: datetime
    values: dict[str, float]


@dataclass(frozen=True, slots=True)
class FeatureTable:
    rows: tuple[EventFeatureRow, ...]

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(row.event_id for row in self.rows)

    def matrix(self, feature_names: tuple[str, ...]) -> np.ndarray:
        return np.asarray(
            [[row.values[name] for name in feature_names] for row in self.rows], dtype=float
        )


HistoryItem = tuple[datetime, bool, int]


def _window_values(
    history: defaultdict[str, deque[HistoryItem]],
    key: str,
    now: datetime,
    window: timedelta,
) -> tuple[HistoryItem, ...]:
    queue = history[key]
    cutoff = now - window
    while queue and queue[0][0] < cutoff:
        queue.popleft()
    return tuple(queue)


def extract_event_features(bundle: DatasetBundle) -> FeatureTable:
    """Extract only information observable at or before each event timestamp."""

    customer_created = {
        entity.entity_id: entity.created_at
        for entity in bundle.entities
        if entity.entity_type is EntityType.CUSTOMER
    }
    customers_by_device: defaultdict[str, set[str]] = defaultdict(set)
    customers_by_ip: defaultdict[str, set[str]] = defaultdict(set)
    customers_by_card: defaultdict[str, set[str]] = defaultdict(set)
    customers_by_address: defaultdict[str, set[str]] = defaultdict(set)
    customers_by_merchant: defaultdict[str, set[str]] = defaultdict(set)
    merchants_by_payout: defaultdict[str, set[str]] = defaultdict(set)
    merchants_by_customer: defaultdict[str, set[str]] = defaultdict(set)
    customer_merchant_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    histories: dict[str, defaultdict[str, deque[HistoryItem]]] = {
        name: defaultdict(deque) for name in ("customer", "device", "ip", "merchant", "payout")
    }
    device_ip_counts: Counter[tuple[str, str]] = Counter()
    projected = nx.Graph()
    seen_customer_infrastructure: set[tuple[str, str]] = set()
    rows: list[EventFeatureRow] = []

    for event in sorted(bundle.events, key=lambda item: (item.timestamp, item.event_id)):
        is_refund = event.event_type is EventType.REFUND
        history_item = (event.timestamp, is_refund, event.amount_minor)
        customer_24h = _window_values(
            histories["customer"], event.customer_id, event.timestamp, timedelta(hours=24)
        )
        customer_1h_count = sum(
            item[0] >= event.timestamp - timedelta(hours=1) for item in customer_24h
        )
        histories["customer"][event.customer_id].append(history_item)

        entity_histories = {}
        for name, key in (
            ("device", event.device_id),
            ("ip", event.ip_id),
            ("merchant", event.merchant_id),
            ("payout", event.merchant_bank_account_id),
        ):
            values = _window_values(histories[name], key, event.timestamp, timedelta(hours=24))
            histories[name][key].append(history_item)
            entity_histories[name] = values + (history_item,)

        projected.add_node(event.customer_id)
        infrastructure = (
            (event.device_id, customers_by_device),
            (event.ip_id, customers_by_ip),
            (event.card_id, customers_by_card),
            (event.address_id, customers_by_address),
        )
        for entity_id, customer_index in infrastructure:
            key = (event.customer_id, entity_id)
            if key not in seen_customer_infrastructure:
                for other_customer in customer_index[entity_id]:
                    if other_customer == event.customer_id:
                        continue
                    current = projected.get_edge_data(event.customer_id, other_customer) or {}
                    projected.add_edge(
                        event.customer_id,
                        other_customer,
                        shared_types=int(current.get("shared_types", 0)) + 1,
                    )
                seen_customer_infrastructure.add(key)
                customer_index[entity_id].add(event.customer_id)

        customers_by_merchant[event.merchant_id].add(event.customer_id)
        merchants_by_payout[event.merchant_bank_account_id].add(event.merchant_id)
        merchants_by_customer[event.customer_id].add(event.merchant_id)
        customer_merchant_counts[event.customer_id][event.merchant_id] += 1

        device_ip_key = (event.device_id, event.ip_id)
        repeated_device_ip = device_ip_counts[device_ip_key]
        device_ip_counts[device_ip_key] += 1

        neighbors = tuple(projected.neighbors(event.customer_id))
        multi_shared_neighbors = sum(
            projected[event.customer_id][neighbor].get("shared_types", 0) >= 2
            for neighbor in neighbors
        )
        component_size = len(nx.node_connected_component(projected, event.customer_id))
        ego_nodes = (event.customer_id, *neighbors)
        local_density = nx.density(projected.subgraph(ego_nodes)) if neighbors else 0.0

        shared_counts = (
            len(customers_by_device[event.device_id]),
            len(customers_by_ip[event.ip_id]),
            len(customers_by_card[event.card_id]),
            len(customers_by_address[event.address_id]),
        )
        total_shared = sum(shared_counts)
        history_15m = {
            name: sum(item[0] >= event.timestamp - timedelta(minutes=15) for item in values)
            for name, values in entity_histories.items()
        }
        customer_values = customer_24h + (history_item,)
        merchant_counts = customer_merchant_counts[event.customer_id]
        values = {
            "amount_log": math.log1p(event.amount_minor),
            "account_age_days": max(
                0.0,
                (event.timestamp - customer_created[event.customer_id]).total_seconds() / 86_400,
            ),
            "is_refund": float(is_refund),
            "is_failed": float(event.status is PaymentStatus.FAILED),
            "hour_sin": math.sin(2 * math.pi * event.timestamp.hour / 24),
            "hour_cos": math.cos(2 * math.pi * event.timestamp.hour / 24),
            "customer_events_1h": float(customer_1h_count + 1),
            "customer_events_24h": float(len(customer_values)),
            "customer_amount_24h_log": math.log1p(sum(item[2] for item in customer_values)),
            "customer_refund_ratio_24h": sum(item[1] for item in customer_values)
            / len(customer_values),
            "retry_count": float(event.metadata.get("retry_count", 0)),
            "shared_device_customers": float(shared_counts[0]),
            "shared_ip_customers": float(shared_counts[1]),
            "shared_card_customers": float(shared_counts[2]),
            "shared_address_customers": float(shared_counts[3]),
            "payout_merchants": float(len(merchants_by_payout[event.merchant_bank_account_id])),
            "merchant_customer_degree": float(len(customers_by_merchant[event.merchant_id])),
            "customer_merchant_degree": float(len(merchants_by_customer[event.customer_id])),
            "infrastructure_customer_max": float(max(shared_counts)),
            "shared_infrastructure_concentration": max(shared_counts) / total_shared,
            "shared_neighbor_count": float(len(neighbors)),
            "multi_shared_neighbor_count": float(multi_shared_neighbors),
            "customer_component_size": float(component_size),
            "customer_local_density": local_density,
            "device_events_15m": float(history_15m["device"]),
            "ip_events_15m": float(history_15m["ip"]),
            "merchant_events_15m": float(history_15m["merchant"]),
            "synchronized_activity_15m": float(max(history_15m.values())),
            "infrastructure_events_24h": float(
                max(len(entity_histories["device"]), len(entity_histories["ip"]))
            ),
            "device_refund_ratio_24h": sum(item[1] for item in entity_histories["device"])
            / len(entity_histories["device"]),
            "merchant_refund_ratio_24h": sum(item[1] for item in entity_histories["merchant"])
            / len(entity_histories["merchant"]),
            "customer_merchant_concentration": max(merchant_counts.values())
            / sum(merchant_counts.values()),
            "repeated_device_ip_events": float(repeated_device_ip),
        }
        rows.append(
            EventFeatureRow(event_id=event.event_id, timestamp=event.timestamp, values=values)
        )

    return FeatureTable(rows=tuple(rows))
