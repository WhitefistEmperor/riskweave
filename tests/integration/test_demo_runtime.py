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
