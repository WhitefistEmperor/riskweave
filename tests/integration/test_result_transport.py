"""Large persisted evidence crosses bounded responses without losing integrity or scope."""

import base64
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.models import AnalysisRun, StoredBlob
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


def test_large_result_fragment_roundtrip_reopen_scope_and_deletion(source):
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
