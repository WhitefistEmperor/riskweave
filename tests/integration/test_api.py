from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from ringsentinel.api.app import create_app


class FakeRuntime:
    def health(self) -> dict[str, Any]:
        return {"status": "ok", "phase": 4}

    def overview(self) -> dict[str, Any]:
        return {"candidate_rings": 1, "synthetic_benchmark": True}

    def benchmark(self) -> dict[str, Any]:
        return {"synthetic_benchmark": True, "models": {"network_aware_hgb": {}}}

    def list_candidates(self) -> list[dict[str, Any]]:
        return [{"candidate_id": "candidate_demo"}]

    def _candidate(self, candidate_id: str) -> dict[str, Any]:
        if candidate_id != "candidate_demo":
            raise KeyError(candidate_id)
        return {"candidate_id": candidate_id}

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._candidate(candidate_id)

    def candidate_graph(self, candidate_id: str) -> dict[str, Any]:
        return {**self._candidate(candidate_id), "nodes": [], "edges": []}

    def candidate_timeline(self, candidate_id: str) -> dict[str, Any]:
        return {**self._candidate(candidate_id), "events": []}

    def candidate_evidence(self, candidate_id: str) -> dict[str, Any]:
        return {"candidate": self._candidate(candidate_id)}

    def simulation(self) -> dict[str, Any]:
        return {"demo_seed": 105, "events": []}

    def hard_negatives(self) -> list[dict[str, Any]]:
        return [{"community_id": "BENIGN_001", "network_aware_flagged": False}]


def test_api_surface_and_not_found_behavior() -> None:
    client = TestClient(create_app(lambda: FakeRuntime()))

    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/overview").json()["candidate_rings"] == 1
    assert client.get("/api/benchmark").json()["synthetic_benchmark"] is True
    assert client.get("/api/candidates").json()[0]["candidate_id"] == "candidate_demo"
    assert client.get("/api/candidates/candidate_demo").status_code == 200
    assert client.get("/api/candidates/candidate_demo/graph").status_code == 200
    assert client.get("/api/candidates/candidate_demo/timeline").status_code == 200
    assert client.get("/api/candidates/candidate_demo/evidence").status_code == 200
    assert client.get("/api/simulation").json()["demo_seed"] == 105
    assert client.get("/api/hard-negatives").json()[0]["network_aware_flagged"] is False
    assert client.get("/api/candidates/missing").status_code == 404
