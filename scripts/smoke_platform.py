"""Real local API smoke; creates isolated synthetic records, never deletes user work."""

import argparse
import json
import time
from uuid import uuid4

import httpx

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--reopen-run", help="Verify a completed run after restarting the backend")
    parser.add_argument("--owner", default="phase5a-smoke")
    args = parser.parse_args()
    # Explicitly scoped to local tests; never upload generated data to an arbitrary host.
    url = httpx.URL(args.base_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Smoke tests require a loopback backend URL")
    with httpx.Client(
        base_url=args.base_url, timeout=30, headers={"X-Development-User": args.owner}
    ) as client:

        def get(path):
            response = client.get(f"/api/v1{path}")
            response.raise_for_status()
            assert response.headers["X-Request-ID"]
            return response.json()

        assert get("/health")["status"] == "ok"
        assert get("/ready")["status"] == "ready"
        assert get("/session")["user_id"] == args.owner
        if args.reopen_run:
            run = get(f"/runs/{args.reopen_run}")
            assert run["status"] == "completed"
            result = get(f"/runs/{run['id']}/results")
            print(
                json.dumps(
                    {
                        "reopened_run": run["id"],
                        "result_checksum": run["result_checksum"],
                        "rings": len(result["rings"]),
                    }
                )
            )
            return
        response = client.post("/api/v1/investigations", json={"name": f"Smoke {uuid4().hex[:8]}"})
        assert response.status_code == 201, response.text
        investigation = response.json()
        inv_id = investigation["id"]
        bundle = SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=1000)).generate()
        path = f"/api/v1/investigations/{inv_id}/artifacts"
        response = client.post(
            path,
            content=bundle.model_dump_json(),
            headers={"Content-Type": "application/json", "X-Filename": "sample.json"},
        )
        assert response.status_code == 201, response.text
        artifact_id = response.json()["id"]
        started = time.monotonic()
        response = client.post(
            f"/api/v1/investigations/{inv_id}/runs",
            json={"artifact_id": artifact_id},
            headers={"Idempotency-Key": uuid4().hex},
        )
        assert response.status_code == 202, response.text
        enqueue_seconds = time.monotonic() - started
        run_id = response.json()["id"]
        states = [response.json()["status"]]
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            run = get(f"/runs/{run_id}")
            if run["status"] != states[-1]:
                states.append(run["status"])
            if run["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)
        assert run["status"] == "completed", run
        assert "running" in states, states
        result = get(f"/runs/{run_id}/results")
        assert result["event_count"] == len(bundle.events)
        rings = get(f"/runs/{run_id}/rings")
        assert rings, "Fixture yielded no candidates; report the measured result"
        candidate_id = rings[0]["candidate_id"]
        evidence = get(f"/runs/{run_id}/rings/{candidate_id}/evidence")
        assert evidence["get_candidate_ring"] == rings[0]
        answer = client.post(
            f"/api/v1/runs/{run_id}/rings/{candidate_id}/investigate",
            json={"question": "Why was this ring flagged?"},
        )
        assert answer.status_code == 200, answer.text
        assert answer.json()["statements"]
        review_path = f"/api/v1/runs/{run_id}/rings/{candidate_id}/review"
        assert get(f"/runs/{run_id}/rings/{candidate_id}/review")["version"] == 0
        review_body = {
            "disposition": "investigating",
            "note": "Synthetic deployment smoke: evidence requires analyst assessment.",
            "expected_version": 0,
        }
        review_headers = {"Idempotency-Key": uuid4().hex}
        for _ in range(2):
            saved = client.post(review_path, json=review_body, headers=review_headers)
            assert saved.status_code == 200, saved.text
            assert saved.json()["version"] == 1
            assert len(saved.json()["history"]) == 1
        review = get(f"/runs/{run_id}/rings/{candidate_id}/review")
        assert review["disposition"] == "investigating"
        assert review["history"][0]["note"] == review_body["note"]
        assert get(f"/runs/{run_id}")["result_checksum"] == run["result_checksum"]
        assert get(f"/runs/{run_id}/results") == result
        review_denied = client.get(
            review_path, headers={"X-Development-User": f"other-{args.owner}"}
        )
        assert review_denied.status_code == 404
        denied = client.get(
            f"/api/v1/runs/{run_id}/results", headers={"X-Development-User": f"other-{args.owner}"}
        )
        assert denied.status_code == 404
        malformed = client.post(
            path, content=b"{broken", headers={"Content-Type": "application/json"}
        )
        assert malformed.status_code == 422
        assert malformed.json()["error"]["code"] == "INVALID_DATASET"
        print(
            json.dumps(
                {
                    "investigation_id": inv_id,
                    "run_id": run_id,
                    "states": states,
                    "enqueue_seconds": round(enqueue_seconds, 4),
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "events": result["event_count"],
                    "entities": result["entity_count"],
                    "candidate_rings": len(rings),
                    "provider": answer.json()["provider"],
                    "review_version": review["version"],
                    "review_history_events": len(review["history"]),
                    "result_checksum": run["result_checksum"],
                    "other_owner_http": denied.status_code,
                    "malformed_http": malformed.status_code,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
