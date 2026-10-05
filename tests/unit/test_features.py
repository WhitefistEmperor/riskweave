from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import pytest

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import EntityType, GenerationConfig
from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    extract_event_features,
)


def test_features_are_causal_and_do_not_read_labels() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=33, transactions=300)).generate()
    full = extract_event_features(bundle)
    cutoff = 100
    truncated_bundle = bundle.model_copy(update={"events": bundle.events[:cutoff]})
    truncated = extract_event_features(truncated_bundle)
    relabeled_bundle = bundle.model_copy(
        update={
            "entity_labels": tuple(
                label.model_copy(update={"is_fraud": not label.is_fraud})
                for label in bundle.entity_labels
            ),
            "event_labels": tuple(
                label.model_copy(update={"is_fraud": not label.is_fraud})
                for label in bundle.event_labels
            ),
        }
    )

    assert truncated.rows == full.rows[:cutoff]
    assert extract_event_features(relabeled_bundle) == full
    forbidden = ("fraud", "ring", "label", "scenario", "archetype")
    assert not any(
        word in name for name in TRANSACTION_FEATURES + NETWORK_FEATURES for word in forbidden
    )


def test_network_features_capture_shared_infrastructure() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=34, transactions=500)).generate()
    table = extract_event_features(bundle)

    assert max(row.values["shared_device_customers"] for row in table.rows) >= 5
    assert max(row.values["shared_ip_customers"] for row in table.rows) >= 5
    assert max(row.values["payout_merchants"] for row in table.rows) >= 3
    assert max(row.values["synchronized_activity_15m"] for row in table.rows) >= 2


@pytest.mark.parametrize(
    "shape", ["generated", "single-device", "overlapping", "many-resources", "bridge"]
)
def test_projected_features_match_independent_causal_graph_oracle(shape):
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=100)).generate()
    first = bundle.events[0]
    other_device = next(
        event.device_id for event in bundle.events if event.device_id != first.device_id
    )
    events = []
    for index, event in enumerate(bundle.events):
        update = {}
        if shape == "single-device":
            update["device_id"] = first.device_id
        elif shape == "overlapping":
            update["device_id"] = first.device_id if index % 2 else other_device
            if index % 3:
                update["ip_id"] = first.ip_id
        elif shape == "many-resources":
            update = {
                "device_id": first.device_id,
                "ip_id": first.ip_id,
                "card_id": first.card_id,
                "address_id": first.address_id,
            }
        elif shape == "bridge":
            update["device_id"] = first.device_id if index < 50 or index > 95 else other_device
        events.append(event.model_copy(update=update))
    bundle = bundle.model_copy(update={"events": tuple(events)})
    rows = {row.event_id: row.values for row in extract_event_features(bundle).rows}
    observed = defaultdict(set)
    customers = set()
    for event in sorted(events, key=lambda item: (item.timestamp, item.event_id)):
        customers.add(event.customer_id)
        for resource in (event.device_id, event.ip_id, event.card_id, event.address_id):
            observed[resource].add(event.customer_id)
        # Rebuild from observed groups rather than using the optimized component
        # tracker or shortcut. This also checks overlapping resource counts.
        pairs = Counter()
        for members in observed.values():
            pairs.update(combinations(sorted(members), 2))
        graph = nx.Graph()
        graph.add_nodes_from(customers)
        for (left, right), count in pairs.items():
            graph.add_edge(left, right, shared_types=count)
        neighbors = list(graph.neighbors(event.customer_id))
        expected = {
            "shared_neighbor_count": len(neighbors),
            "multi_shared_neighbor_count": sum(
                graph[event.customer_id][neighbor]["shared_types"] >= 2 for neighbor in neighbors
            ),
            "customer_component_size": len(nx.node_connected_component(graph, event.customer_id)),
            "customer_local_density": nx.density(graph.subgraph([event.customer_id, *neighbors])),
        }
        assert {name: rows[event.event_id][name] for name in expected} == expected


def test_shared_device_features_avoid_repeated_component_and_clique_traversals(monkeypatch):
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=100)).generate()
    device = bundle.events[0].device_id
    bundle = bundle.model_copy(
        update={
            "events": tuple(
                event.model_copy(update={"device_id": device}) for event in bundle.events
            )
        }
    )

    def traversal(*_):
        pytest.fail("Dense feature extraction repeated a graph traversal")

    monkeypatch.setattr(nx, "node_connected_component", traversal)
    monkeypatch.setattr(nx, "density", traversal)
    monkeypatch.setattr(nx, "Graph", traversal)
    table = extract_event_features(bundle)
    assert all(row.values["customer_local_density"] in {0.0, 1.0} for row in table.rows)
    assert max(row.values["customer_component_size"] for row in table.rows) > 2


def test_late_resource_bridge_merges_only_observed_components():
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=100)).generate()
    ids = {
        kind: [entity.entity_id for entity in bundle.entities if entity.entity_type is kind][:3]
        for kind in (
            EntityType.CUSTOMER,
            EntityType.DEVICE,
            EntityType.IP,
            EntityType.CARD,
            EntityType.ADDRESS,
        )
    }
    events = []
    for original, customer, device in zip(
        bundle.events[:4], (0, 1, 2, 1), (0, 0, 1, 1), strict=True
    ):
        events.append(
            original.model_copy(
                update={
                    "customer_id": ids[EntityType.CUSTOMER][customer],
                    "device_id": ids[EntityType.DEVICE][device],
                    "ip_id": ids[EntityType.IP][customer],
                    "card_id": ids[EntityType.CARD][customer],
                    "address_id": ids[EntityType.ADDRESS][customer],
                }
            )
        )
    rows = extract_event_features(bundle.model_copy(update={"events": tuple(events)})).rows
    assert [row.values["customer_component_size"] for row in rows] == [1, 2, 1, 3]
    assert [row.values["shared_neighbor_count"] for row in rows] == [0, 1, 0, 2]
    assert [row.values["multi_shared_neighbor_count"] for row in rows] == [0, 0, 0, 0]
    assert rows[-1].values["customer_local_density"] == (2 / (3 * 2)) * 2
