"""Evidence cache over real persisted sections: ownership, measured hits, erasure, outage."""

import time

import pytest
from fastapi.testclient import TestClient

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform import result_sections
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.evidence_cache import EvidenceCache, RedisBackend
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings


def payload(transactions=100):
    return (
        SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=transactions))
        .generate()
        .model_dump_json()
        .encode()
    )


def ring(candidate_id):
    return {
        "candidate": {
            "candidate_id": candidate_id,
            "risk_score": 0.9,
            "first_suspicious_timestamp": "2026-01-01T00:00:00Z",
            "estimated_exposure_minor": 10,
            "suspicious_relationships": [],
            "evidence": {},
            "member_entity_ids": ["m"],
            "related_event_ids": [],
        },
        "queries": {"sample": {"text": f"evidence for {candidate_id}"}},
    }


@pytest.fixture(params=["local", "database"])
def saved(tmp_path, request):
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'cache.db'}",
        storage_root=tmp_path / "objects",
        storage_backend=request.param,
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    service = InvestigationService(db, storage_for(db, settings), settings)
    owner = Principal("cache-owner")
    case = service.create(owner, "Cache control")
    artifact = service.attach(owner, case.id, payload(), "input.json", "application/json")
    run = service.start(owner, case.id, artifact.id, "cache-control")
    service.claim()
    result = {
        "currency": "INR",
        "schema_version": "1",
        "event_count": 100,
        "entity_count": 100,
        "threshold": 0.7,
        "model_scope": "Cache fixture",
        "rings": [ring("first"), ring("second")],
    }
    service.finish(run.id, result)
    yield service, owner, case, run.id, result
    db.engine.dispose()


def count_reads(monkeypatch):
    calls = []
    original = result_sections.read

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(result_sections, "read", counting)
    return calls


def test_repeat_reads_hit_cache_and_skip_storage(saved, monkeypatch):
    service, owner, _, run_id, result = saved
    reads = count_reads(monkeypatch)
    for _ in range(5):
        assert (
            result_sections.value(service, owner, run_id, "first", "evidence")
            == result["rings"][0]["queries"]
        )
        assert result_sections.currency(service, owner, run_id) == "INR"
    # First pass: candidate check + evidence + currency. Every later pass is served cached.
    assert len(reads) == 3
    stats = service.evidence_cache.stats()
    assert stats["hits"] == 12 and stats["misses"] == 3 and stats["hit_ratio"] == 0.8


def test_cached_entries_never_cross_owners(saved):
    service, owner, _, run_id, _ = saved
    result_sections.value(service, owner, run_id, "first", "evidence")
    hits = service.evidence_cache.counters["hits"]
    with pytest.raises(ProductError) as denied:
        result_sections.value(service, Principal("intruder"), run_id, "first", "evidence")
    assert denied.value.code == "NOT_FOUND"
    # Denied before any cache lookup.
    assert service.evidence_cache.counters["hits"] == hits
    with pytest.raises(ProductError) as missing:
        result_sections.value(service, owner, run_id, "absent", "evidence")
    assert missing.value.code == "NOT_FOUND"


def test_deletion_purges_cached_evidence(saved):
    service, owner, case, run_id, _ = saved
    result_sections.value(service, owner, run_id, "second", "evidence")
    assert len(service.evidence_cache.backend) == 2
    assert DeletionService(service).remove(owner, case.id, case.name)["status"] == "deleted"
    assert len(service.evidence_cache.backend) == 0
    assert service.evidence_cache.counters["invalidated"] == 2
    with pytest.raises(ProductError) as gone:
        result_sections.value(service, owner, run_id, "second", "evidence")
    assert gone.value.code == "NOT_FOUND"


class DownRedis:
    def __getattr__(self, _):
        def fail(*_, **__):
            raise ConnectionError("unreachable")

        return fail


def test_cache_outage_serves_authoritative_bytes(saved, monkeypatch):
    service, owner, case, run_id, result = saved
    service.evidence_cache = EvidenceCache(RedisBackend(DownRedis()))
    reads = count_reads(monkeypatch)
    for _ in range(3):
        assert (
            result_sections.value(service, owner, run_id, "first", "evidence")
            == result["rings"][0]["queries"]
        )
    assert len(reads) == 6  # candidate + evidence each time, straight from storage
    assert service.evidence_cache.counters["errors"] == 1
    assert DeletionService(service).remove(owner, case.id, case.name)["status"] == "deleted"


def test_investigator_answers_are_cached_per_owner_and_question(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        storage_root=tmp_path / "objects",
        jobs_enabled=True,
    )
    database = Database(settings.database_url.get_secret_value())
    database.migrate()
    database.engine.dispose()
    application = create_app(settings=settings)
    with TestClient(application) as client:
        client.headers["X-Development-User"] = "answer-owner"
        inv = client.post("/api/v1/investigations", json={"name": "Answers"}).json()["id"]
        artifact = client.post(
            f"/api/v1/investigations/{inv}/artifacts",
            content=payload(),
            headers={"Content-Type": "application/json", "X-Filename": "s.json"},
        ).json()["id"]
        run_id = client.post(
            f"/api/v1/investigations/{inv}/runs",
            json={"artifact_id": artifact},
            headers={"Idempotency-Key": "cache"},
        ).json()["id"]
        deadline = time.monotonic() + 180
        while client.get(f"/api/v1/runs/{run_id}").json()["status"] not in {
            "completed",
            "failed",
        }:
            assert time.monotonic() < deadline
            time.sleep(0.1)
        rings = client.get(f"/api/v1/runs/{run_id}/rings").json()
        assert rings
        prefix = f"/api/v1/runs/{run_id}/rings/{rings[0]['candidate_id']}"
        cache = application.state.platform.evidence_cache
        first = client.post(f"{prefix}/investigate", json={"question": "Why was this flagged?"})
        stores = cache.counters["stores"]
        hits = cache.counters["hits"]
        second = client.post(f"{prefix}/investigate", json={"question": "Why was this flagged?"})
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert cache.counters["stores"] == stores  # served from cache, nothing recomputed
        assert cache.counters["hits"] > hits
        other = client.post(f"{prefix}/investigate", json={"question": "How much exposure?"})
        assert other.status_code == 200 and other.json()["question"] == "How much exposure?"
        client.headers["X-Development-User"] = "someone-else"
        denied = client.post(f"{prefix}/investigate", json={"question": "Why was this flagged?"})
        assert denied.status_code == 404


def test_uncached_reads_still_fail_closed_on_storage_corruption(saved, monkeypatch):
    service, owner, _, run_id, result = saved
    original = service.storage.read_range

    def corrupt(key, offset, length):
        part = bytearray(original(key, offset, length))
        part[-1] ^= 1
        return bytes(part)

    monkeypatch.setattr(service.storage, "read_range", corrupt)
    with pytest.raises(ProductError) as failure:
        result_sections.value(service, owner, run_id, "first", "evidence")
    assert failure.value.code == "INTERNAL_ERROR"
    # Nothing unverified was cached; once storage is healthy the true bytes are served.
    monkeypatch.setattr(service.storage, "read_range", original)
    assert (
        result_sections.value(service, owner, run_id, "first", "evidence")
        == result["rings"][0]["queries"]
    )
