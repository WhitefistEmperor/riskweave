"""Large persisted evidence crosses bounded responses without losing integrity or scope."""

import base64
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import AnalysisRun, ResultFragment, StoredBlob
from ringsentinel.platform.result_fragments import index_existing
from ringsentinel.platform.result_transport import CHUNK_BYTES, ResultTransport
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings


@pytest.fixture(params=["local", "database"])
def source(tmp_path, request):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'transport.db'}",
        storage_root=tmp_path / "objects",
        storage_backend=request.param,
        jobs_enabled=False,
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    service = InvestigationService(db, storage_for(db, settings), settings)
    owner = Principal("transport-owner")
    case = service.create(owner, "Transport-only fixture")
    content = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    artifact = service.attach(owner, case.id, content, "input.json", "application/json")
    run = service.start(owner, case.id, artifact.id, "transport")
    yield settings, service, owner, case, run
    db.engine.dispose()


def test_large_result_fragment_roundtrip_reopen_scope_and_deletion(source, monkeypatch):
    settings, service, owner, case, run = source
    assert service.claim() == run.id
    # A transport fixture, not model accuracy evidence. This serializes above 4.5MB.
    original = {
        "schema_version": "1",
        "threshold": 0.5,
        "event_count": 0,
        "entity_count": 0,
        "model_scope": "é😀" * 300_000,
        "rings": [],
    }
    service.finish(run.id, original)
    raw = service.result_content(owner, run.id)
    assert len(raw) > 4_500_000
    with TestClient(create_app(settings=settings)) as client:
        client.headers["X-Development-User"] = owner.user_id
        path = f"/api/v1/runs/{run.id}/results"
        with monkeypatch.context() as patch:
            patch.setattr(
                client.app.state.platform.storage,
                "read",
                lambda *_: pytest.fail("Oversized inline request read the full result"),
            )
            inline = client.get(path)
            assert inline.status_code == 409
            assert inline.json()["error"]["code"] == "RESULT_TRANSPORT_REQUIRED"
            client.headers["X-Development-User"] = "another-owner"
            assert client.get(path).status_code == 404
            client.headers["X-Development-User"] = owner.user_id
        manifest = client.get(f"{path}/manifest")
        assert manifest.status_code == 200, manifest.text
        info = manifest.json()
        assert info["run_id"] == run.id and info["investigation_id"] == case.id
        assert info["sha256"] == service.run(owner, run.id).result_checksum
        assert info["size_bytes"] == len(raw)
        assert not {"storage_key", "result_reference", "url"}.intersection(info)
        pieces = []
        for index in range(info["chunk_count"]):
            response = client.get(f"{path}/chunks/{index}")
            assert response.status_code == 200, response.text
            assert len(response.content) < 4_500_000
            part = response.json()
            data = base64.b64decode(part["data"], validate=True)
            assert len(data) == part["size_bytes"] <= 2_000_000
            assert part["index"] == index and part["run_id"] == run.id
            assert part["result_sha256"] == info["sha256"]
            assert hashlib.sha256(data).hexdigest() == part["sha256"]
            pieces.append(data)
        joined = b"".join(pieces)
        assert joined == raw and json.loads(joined) == original
        for index in [-1, info["chunk_count"], 1_000_000]:
            assert client.get(f"{path}/chunks/{index}").status_code == 404
        client.headers["X-Development-User"] = "another-owner"
        for suffix in ["manifest", "chunks/0", "chunks/-1"]:
            assert client.get(f"{path}/{suffix}").status_code == 404
        client.headers["X-Development-User"] = owner.user_id
        DeletionService(service).remove(owner, case.id, case.name)
        assert client.get(f"{path}/chunks/0").status_code == 404
        assert client.get(f"{path}/manifest").status_code == 404


def test_unfinished_and_corrupt_sources_never_publish_chunks(source):
    settings, service, owner, _, run = source
    path = f"/api/v1/runs/{run.id}/results"
    with TestClient(create_app(settings=settings)) as client:
        client.headers["X-Development-User"] = owner.user_id
        for suffix in ["manifest", "chunks/0"]:
            assert client.get(f"{path}/{suffix}").status_code == 409
        service.claim()
        service.finish(run.id, {"rings": []})
        with service.database.session() as session:
            key = session.get(AnalysisRun, run.id).result_reference
        if settings.storage_backend == "database":
            with service.database.write() as session:
                obj = session.scalar(select(StoredBlob).where(StoredBlob.key == key))
                obj.content = b"changed bytes"
        else:
            (settings.storage_root / key).write_bytes(b"changed bytes")
        for suffix in ["manifest", "chunks/0"]:
            response = client.get(f"{path}/{suffix}")
            assert response.status_code == 500
            assert "changed bytes" not in response.text


def test_indexed_fragments_do_not_read_full_objects_and_erasure_removes_digests(
    source, monkeypatch
):
    _, service, owner, case, run = source
    service.claim()
    service.finish(run.id, {"rings": [], "fixture": "x" * 4_000_011})
    raw = service.result_content(owner, run.id)
    ranges = []
    original_range = service.storage.read_range

    def bounded_range(key, offset, length):
        ranges.append((offset, length))
        return original_range(key, offset, length)

    monkeypatch.setattr(service.storage, "read", lambda *_: pytest.fail("Whole result read"))
    monkeypatch.setattr(service.storage, "read_range", bounded_range)
    transport = ResultTransport(service)
    info = transport.manifest(owner, run.id)
    parts = [
        base64.b64decode(transport.chunk(owner, run.id, index)["data"])
        for index in range(info["chunk_count"])
    ]
    assert b"".join(parts) == raw
    assert sum(length for _, length in ranges) == len(raw) + CHUNK_BYTES
    assert max(length for _, length in ranges) == CHUNK_BYTES
    with service.database.session() as session:
        rows = list(session.scalars(select(ResultFragment).where(ResultFragment.run_id == run.id)))
        assert len(rows) == info["chunk_count"]
    DeletionService(service).remove(owner, case.id, case.name)
    with service.database.session() as session:
        assert (
            list(session.scalars(select(ResultFragment).where(ResultFragment.run_id == run.id)))
            == []
        )


def test_later_part_corruption_fails_without_claiming_manifest_is_full_integrity(source):
    settings, service, owner, _, run = source
    service.claim()
    service.finish(run.id, {"rings": [], "fixture": "x" * 2_000_100})
    raw = bytearray(service.result_content(owner, run.id))
    raw[CHUNK_BYTES + 10] ^= 1
    saved = service.run(owner, run.id)
    if settings.storage_backend == "database":
        with service.database.write() as session:
            session.get(StoredBlob, saved.result_reference).content = bytes(raw)
    else:
        with (settings.storage_root / saved.result_reference).open("r+b") as stream:
            stream.seek(CHUNK_BYTES + 10)
            stream.write(bytes(raw[CHUNK_BYTES + 10 : CHUNK_BYTES + 11]))
    transport = ResultTransport(service)
    assert transport.manifest(owner, run.id)["chunk_count"] == 2
    transport.chunk(owner, run.id, 0)
    with pytest.raises(ProductError) as failed:
        transport.chunk(owner, run.id, 1)
    assert failed.value.code == "INTERNAL_ERROR"


def test_legacy_result_fallback_preserves_checksums_and_incomplete_index_is_not_silently_rebuilt(
    source,
):
    _, service, owner, _, run = source
    service.claim()
    service.finish(run.id, {"rings": []})
    raw = service.result_content(owner, run.id)
    transport = ResultTransport(service)
    with service.database.write() as session:
        session.execute(delete(ResultFragment).where(ResultFragment.run_id == run.id))
    with pytest.raises(ProductError):
        transport.manifest(owner, run.id)
    with service.database.write() as session:
        session.get(AnalysisRun, run.id).result_size_bytes = None
    info = transport.manifest(owner, run.id)
    part = transport.chunk(owner, run.id, 0)
    assert info["sha256"] == hashlib.sha256(raw).hexdigest()
    assert base64.b64decode(part["data"]) == raw


def test_explicit_legacy_indexing_is_idempotent_and_preserves_evidence(source, monkeypatch):
    _, service, owner, _, run = source
    service.claim()
    service.finish(run.id, {"rings": [], "fixture": "backfill-control"})
    checksum = service.run(owner, run.id).result_checksum
    raw = service.result_content(owner, run.id)
    with service.database.write() as session:
        session.execute(delete(ResultFragment).where(ResultFragment.run_id == run.id))
        session.get(AnalysisRun, run.id).result_size_bytes = None
    with pytest.raises(ValueError):
        index_existing(service)
    assert index_existing(service, writers_stopped=True, limit=1) == 1
    assert index_existing(service, writers_stopped=True, limit=1) == 0
    assert service.run(owner, run.id).result_checksum == checksum
    assert service.result_content(owner, run.id) == raw
    monkeypatch.setattr(
        service.storage, "read", lambda *_: pytest.fail("Indexed fallback full read")
    )
    assert ResultTransport(service).manifest(owner, run.id)["sha256"] == checksum


def test_legacy_indexing_refuses_active_and_corrupt_data_without_creating_digests(source):
    settings, service, owner, _, run = source
    with pytest.raises(ValueError, match="Active analysis"):
        index_existing(service, writers_stopped=True)
    service.claim()
    service.finish(run.id, {"rings": []})
    key = service.run(owner, run.id).result_reference
    with service.database.write() as session:
        session.execute(delete(ResultFragment).where(ResultFragment.run_id == run.id))
        session.get(AnalysisRun, run.id).result_size_bytes = None
        if settings.storage_backend == "database":
            session.get(StoredBlob, key).content = b"corrupt"
    if settings.storage_backend == "local":
        (settings.storage_root / key).write_bytes(b"corrupt")
    with pytest.raises(ProductError):
        index_existing(service, writers_stopped=True)
    with service.database.session() as session:
        assert session.get(AnalysisRun, run.id).result_size_bytes is None
        assert (
            list(session.scalars(select(ResultFragment).where(ResultFragment.run_id == run.id)))
            == []
        )
