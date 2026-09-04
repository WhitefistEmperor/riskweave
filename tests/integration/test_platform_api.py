"""HTTP contracts, owner isolation, real scheduler execution, and restart persistence."""

import json
import logging
import time

import pytest
from fastapi.testclient import TestClient

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform.database import Database
from ringsentinel.platform.settings import Settings


@pytest.fixture
def settings(tmp_path):
    result = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        storage_root=tmp_path / "objects",
        jobs_enabled=False,
    )
    database = Database(result.database_url.get_secret_value())
    database.migrate()
    database.engine.dispose()
    return result


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings=settings)) as result:
        yield result


@pytest.fixture(scope="module")
def dataset_bytes():
    return (
        SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )


def create(client):
    response = client.post("/api/v1/investigations", json={"name": "Review"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, investigation_id, dataset_bytes):
    response = client.post(
        f"/api/v1/investigations/{investigation_id}/artifacts",
        content=dataset_bytes,
        headers={"Content-Type": "application/json", "X-Filename": "sample.json"},
    )
    assert response.status_code == 201, response.text
    assert "storage_key" not in response.json()
    return response.json()["id"]


def start(client, investigation_id, artifact_id, key="first"):
    return client.post(
        f"/api/v1/investigations/{investigation_id}/runs",
        json={"artifact_id": artifact_id},
        headers={"Idempotency-Key": key},
    )


def assert_error(response, code, status):
    assert response.status_code == status, response.text
    assert set(response.json()) == {"error"}
    detail = response.json()["error"]
    assert set(detail) == {"code", "message", "request_id"}
    assert detail["code"] == code
    assert detail["request_id"] == response.headers["X-Request-ID"]


def test_health_readiness_and_explicit_migration(settings, tmp_path):
    unmigrated = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'unmigrated.db'}",
        storage_root=tmp_path / "new-objects",
        jobs_enabled=False,
    )
    with TestClient(create_app(settings=unmigrated)) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert_error(client.get("/api/v1/ready"), "NOT_READY", 503)
    database = Database(unmigrated.database_url.get_secret_value())
    database.migrate()
    database.engine.dispose()
    with TestClient(create_app(settings=unmigrated)) as client:
        assert client.get("/api/v1/ready").json()["status"] == "ready"


def test_http_owner_isolation_and_duplicate_prevention(client, dataset_bytes):
    client.headers["X-Development-User"] = "alice"
    assert client.get("/api/v1/session").json() == {
        "user_id": "alice",
        "authentication_mode": "development",
        "production_authentication": False,
    }
    inv = create(client)
    artifact = upload(client, inv, dataset_bytes)
    assert upload(client, inv, dataset_bytes) == artifact
    first = start(client, inv, artifact)
    assert first.status_code == 202
    run = first.json()
    assert run["status"] == "queued"
    assert run["created_at"].endswith("Z")
    assert "result_reference" not in run and "active_slot" not in run
    assert start(client, inv, artifact).json()["id"] == run["id"]
    assert_error(start(client, inv, artifact, "duplicate"), "CONFLICT", 409)
    assert_error(client.get(f"/api/v1/runs/{run['id']}/results"), "CONFLICT", 409)
    assert len(client.get(f"/api/v1/investigations/{inv}/runs").json()) == 1
    assert len(client.get(f"/api/v1/investigations/{inv}/artifacts").json()) == 1
    client.headers["X-Development-User"] = "bob"
    assert client.get("/api/v1/investigations").json() == []
    for path in [
        f"/investigations/{inv}",
        f"/investigations/{inv}/artifacts",
        f"/investigations/{inv}/runs",
        f"/runs/{run['id']}",
        f"/runs/{run['id']}/results",
        f"/runs/{run['id']}/rings",
        f"/runs/{run['id']}/rings/guessed",
        f"/runs/{run['id']}/rings/guessed/evidence",
    ]:
        assert_error(client.get(f"/api/v1{path}"), "NOT_FOUND", 404)
    assert_error(start(client, inv, artifact), "NOT_FOUND", 404)
    assert_error(
        client.post(
            f"/api/v1/runs/{run['id']}/rings/guessed/investigate", json={"question": "why?"}
        ),
        "NOT_FOUND",
        404,
    )
    assert_error(
        client.post(
            f"/api/v1/investigations/{inv}/artifacts",
            content=dataset_bytes,
            headers={"Content-Type": "application/json"},
        ),
        "NOT_FOUND",
        404,
    )


def test_upload_validation_stream_limit_and_safe_failures(
    client, dataset_bytes, monkeypatch, caplog
):
    inv = create(client)
    for body in ({}, {"name": " "}, {"name": "x", "owner_id": "other"}):
        assert_error(client.post("/api/v1/investigations", json=body), "VALIDATION_ERROR", 422)
    endpoint = f"/api/v1/investigations/{inv}/artifacts"
    for body, filename, content_type in [
        (b"{broken", "sample.json", "application/json"),
        (dataset_bytes, "../../secret.json", "application/json"),
        (dataset_bytes, "C:\\secret.json", "application/json"),
        (dataset_bytes, "sample.csv", "text/csv"),
    ]:
        assert_error(
            client.post(
                endpoint,
                content=body,
                headers={
                    "Content-Type": content_type,
                    "X-Filename": filename,
                },
            ),
            "INVALID_DATASET",
            422,
        )
    client.app.state.settings.upload_limit_bytes = 1024
    assert_error(
        client.post(
            endpoint,
            content=dataset_bytes,
            headers={
                "Content-Type": "application/json",
            },
        ),
        "UPLOAD_TOO_LARGE",
        413,
    )
    assert_error(
        client.post(
            endpoint,
            content=iter([b"{" * 600, b"x" * 600]),
            headers={
                "Content-Type": "application/json",
            },
        ),
        "UPLOAD_TOO_LARGE",
        413,
    )
    assert client.get(f"/api/v1/investigations/{inv}/artifacts").json() == []

    def failing_list(principal):
        raise RuntimeError("password=secret C:/private/data.json")

    monkeypatch.setattr(client.app.state.platform, "list", failing_list)
    with caplog.at_level(logging.INFO, logger="ringsentinel.http"):
        response = client.get(
            "/api/v1/investigations?token=private",
            headers={
                "Origin": "http://127.0.0.1:5173",
            },
        )
    assert_error(response, "INTERNAL_ERROR", 500)
    assert "private" not in response.text and "password" not in response.text
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5173"
    entry = json.loads(caplog.records[-1].message)
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["route"] == "/api/v1/investigations"
    assert entry["failure_category"] == "INTERNAL_ERROR"
    assert "private" not in entry.values()


def test_schema_and_missing_or_invalid_session(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/runs/{run_id}/results"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ResultsResponse",
    }
    assert operation["responses"]["404"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse",
    }
    assert_error(client.get("/api/v1/investigations/not-a-real-id"), "NOT_FOUND", 404)
    assert_error(
        client.get(
            "/api/v1/session",
            headers={
                "X-Development-User": "invalid/user",
            },
        ),
        "UNAUTHORIZED",
        401,
    )


def test_production_fails_closed_and_cors_is_restricted(settings):
    prod = Settings(
        environment="production",
        auth_mode="disabled",
        demo_enabled=False,
        database_url=settings.database_url,
        storage_root=settings.storage_root,
        frontend_origins=["https://analyst.example"],
        jobs_enabled=False,
    )
    with TestClient(create_app(settings=prod)) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert_error(
            client.get(
                "/api/v1/session",
                headers={
                    "X-Development-User": "admin",
                    "Authorization": "Bearer fake",
                },
            ),
            "UNAUTHORIZED",
            401,
        )
        assert_error(client.get("/api/v1/investigations"), "UNAUTHORIZED", 401)
        assert_error(client.get("/api/overview"), "NOT_FOUND", 404)
        allowed = client.options(
            "/api/v1/investigations",
            headers={
                "Origin": "https://analyst.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Request-ID,Content-Type",
            },
        )
        assert allowed.headers["Access-Control-Allow-Origin"] == "https://analyst.example"
        assert allowed.headers["X-Request-ID"]
        assert "x-request-id" in allowed.headers["Access-Control-Allow-Headers"].lower()
        denied = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
        assert "Access-Control-Allow-Origin" not in denied.headers


def test_real_http_scheduler_completion_evidence_and_reopen(settings, dataset_bytes):
    settings.jobs_enabled = True
    application = create_app(settings=settings)
    with TestClient(application) as client:
        assert client.get("/api/v1/ready").status_code == 200
        client.headers["X-Development-User"] = "scheduler-owner"
        inv = create(client)
        artifact = upload(client, inv, dataset_bytes)
        started = time.monotonic()
        response = start(client, inv, artifact)
        assert response.status_code == 202
        assert time.monotonic() - started < 5, "Run creation must not execute the detector"
        run_id = response.json()["id"]
        statuses = {response.json()["status"]}
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            run = client.get(f"/api/v1/runs/{run_id}").json()
            statuses.add(run["status"])
            if run["status"] in {"completed", "failed"}:
                break
            assert client.get("/api/v1/health").status_code == 200
            time.sleep(0.1)
        assert statuses == {"queued", "running", "completed"}, run
        assert run["started_at"].endswith("Z") and run["completed_at"].endswith("Z")
        result = client.get(f"/api/v1/runs/{run_id}/results")
        assert result.status_code == 200, result.text
        rings = client.get(f"/api/v1/runs/{run_id}/rings").json()
        assert rings, "The generated known scenario sample should yield measured candidates"
        candidate_id = rings[0]["candidate_id"]
        prefix = f"/api/v1/runs/{run_id}/rings/{candidate_id}"
        evidence = client.get(f"{prefix}/evidence")
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["get_candidate_ring"] == rings[0]
        assert evidence.json()["get_transaction_timeline"]
        answer = client.post(f"{prefix}/investigate", json={"question": "Why was this flagged?"})
        assert answer.status_code == 200, answer.text
        assert answer.json()["statements"]
        assert answer.json()["provider"] == "deterministic_evidence_fallback"
        assert_error(client.get(f"/api/v1/runs/{run_id}/rings/missing"), "NOT_FOUND", 404)
        original_result = result.json()
    settings.jobs_enabled = False
    with TestClient(create_app(settings=settings)) as reopened:
        reopened.headers["X-Development-User"] = "scheduler-owner"
        assert reopened.get(f"/api/v1/investigations/{inv}").json()["status"] == "completed"
        assert reopened.get(f"/api/v1/runs/{run_id}/results").json() == original_result
        reopened.headers["X-Development-User"] = "another-owner"
        assert_error(reopened.get(f"/api/v1/runs/{run_id}/results"), "NOT_FOUND", 404)


def test_real_http_scheduler_failure_is_pollable(settings, dataset_bytes):
    settings.jobs_enabled = True
    settings.analysis_timeout_seconds = 1
    with TestClient(create_app(settings=settings)) as client:
        inv = create(client)
        artifact = upload(client, inv, dataset_bytes)
        response = start(client, inv, artifact)
        assert response.status_code == 202
        run_id = response.json()["id"]
        states = {response.json()["status"]}
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            run = client.get(f"/api/v1/runs/{run_id}").json()
            states.add(run["status"])
            if run["status"] == "failed":
                break
            time.sleep(0.05)
        assert states == {"queued", "running", "failed"}, run
        assert run["error_code"] == "ANALYSIS_TIMEOUT"
        assert run["error_message_safe"] == "Analysis exceeded its execution time limit."
        assert client.get(f"/api/v1/investigations/{inv}").json()["status"] == "failed"
        assert_error(client.get(f"/api/v1/runs/{run_id}/results"), "CONFLICT", 409)
