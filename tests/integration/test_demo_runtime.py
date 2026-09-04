"""Exercise actual JSON serialization and replay facts, not only route stubs."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from ringsentinel.api.app import create_app
from ringsentinel.api.runtime import DemoRuntime


@pytest.fixture(scope="module")
def runtime() -> DemoRuntime:
    return DemoRuntime()


def test_real_runtime_routes_and_replay_prefix(runtime: DemoRuntime) -> None:
    client = TestClient(create_app(lambda: runtime))
    for path in ("overview", "benchmark", "candidates", "hard-negatives", "simulation"):
        response = client.get(f"/api/{path}")
        assert response.status_code == 200, path
    stream = client.get("/api/simulation").json()
    events = stream["events"]
    keys = [(item["timestamp"], item["event_id"]) for item in events]
    assert keys == sorted(keys)
    assert events[0]["candidate_state"] is None
    first = next(item for item in events if item["candidate_state"])
    assert first["timestamp"] == stream["first_alert_timestamp"]
    assert (
        datetime.fromisoformat(first["timestamp"])
        - datetime.fromisoformat(stream["attack_start_timestamp"])
    ).total_seconds() == 480
    for item in events:
        if item["candidate_state"]:
            assert item["candidate_state"]["events"] <= item["observed_event_count"]
    candidate_id = stream["candidate_id"]
    for suffix in ("", "/graph", "/timeline", "/evidence"):
        assert client.get(f"/api/candidates/{candidate_id}{suffix}").status_code == 200


def test_snapshot_evidence_never_contains_future_events(runtime: DemoRuntime) -> None:
    client = TestClient(create_app(lambda: runtime))
    first = next(item for item in runtime.simulation()["events"] if item["candidate_state"])
    count = first["observed_event_count"]
    candidate_id = first["candidate_state"]["candidate_id"]
    response = client.get(
        "/api/snapshot", params={"event_count": count, "candidate_id": candidate_id}
    )
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["scope"] == "observed_prefix"
    assert snapshot["as_of"] == first["timestamp"]
    detail = snapshot["selected"]
    prefix_ids = {
        event.event_id
        for event in sorted(
            runtime.bundle.events, key=lambda event: (event.timestamp, event.event_id)
        )[:count]
    }
    assert set(detail["candidate"]["related_event_ids"]) <= prefix_ids
    assert all(event["timestamp"] <= snapshot["as_of"] for event in detail["timeline"]["events"])
    precursor = next(
        event for event in detail["timeline"]["events"] if event["kind"] == "candidate_created"
    )
    assert precursor["risk_score"] is None
    assert precursor["timestamp"] >= detail["candidate"]["first_suspicious_timestamp"]
    assert client.get("/api/snapshot", params={"event_count": 0}).status_code == 422
    assert client.get("/api/snapshot", params={"event_count": 999999}).status_code == 422
    assert (
        client.get(
            "/api/snapshot", params={"event_count": 1, "candidate_id": candidate_id}
        ).status_code
        == 404
    )
