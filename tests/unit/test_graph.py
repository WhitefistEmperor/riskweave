from __future__ import annotations

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import GenerationConfig
from ringsentinel.graph.builder import build_temporal_graph


def test_temporal_graph_builds_entity_event_nodes_and_relationship_indexes() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=31, transactions=300)).generate()
    temporal_graph = build_temporal_graph(bundle)

    assert temporal_graph.graph.number_of_nodes() == len(bundle.entities) + len(bundle.events)
    assert temporal_graph.graph.number_of_edges() >= len(bundle.events) * 12
    assert any(len(customers) >= 5 for customers in temporal_graph.customers_by_device.values())
    assert any(len(customers) >= 5 for customers in temporal_graph.customers_by_ip.values())
    assert any(len(merchants) >= 3 for merchants in temporal_graph.merchants_by_payout.values())

    customer_id = bundle.events[0].customer_id
    related = temporal_graph.related_events(customer_id)
    assert related
    assert all(event.customer_id == customer_id for event in related)


def test_temporal_graph_honors_as_of_timestamp() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=32, transactions=300)).generate()
    cutoff = bundle.events[len(bundle.events) // 2].timestamp
    graph = build_temporal_graph(bundle, until=cutoff)

    assert graph.event_by_id
    assert all(event.timestamp <= cutoff for event in graph.event_by_id.values())
    assert len(graph.event_by_id) < len(bundle.events)
