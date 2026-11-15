"""A large real upload survives retries and commits without doubling its quota."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform.backup import create_snapshot
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.models import Status, StoredBlob, UploadPart, UploadSession
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings

CHUNK = 2_000_000


@pytest.fixture
def source(tmp_path):
    dataset = (
        SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    content = dataset + b" " * (4_700_000 - len(dataset))
    config = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'uploads.db'}",
        storage_root=tmp_path / "scratch",
        storage_backend="database",
        execution_mode="request",
        analysis_timeout_seconds=240,
        jobs_enabled=False,
        storage_limit_bytes=6_000_000,
    )
    database = Database(config.database_url.get_secret_value())
    database.migrate()
    owner = Principal("alice")
    service = InvestigationService(database, storage_for(database, config), config)
    case = service.create(owner, "Large file")
    yield config, service, owner, case, content, tmp_path
    database.engine.dispose()


def begin(client, case_id, content, key="same", name="large.json"):
    return client.post(
        f"/api/v1/investigations/{case_id}/uploads",
        json={
            "name": name,
            "size_bytes": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
        },
        headers={"Idempotency-Key": key},
    )


def send(client, case_id, upload_id, index, part):
    return client.put(
        f"/api/v1/investigations/{case_id}/uploads/{upload_id}/parts/{index}",
        content=part,
        headers={"X-Chunk-SHA256": hashlib.sha256(part).hexdigest()},
    )


def test_large_http_upload_resumes_across_instances_and_erases_bytes(source):
    config, service, owner, case, content, _ = source
    with TestClient(create_app(settings=config)) as client:
        client.headers["X-Development-User"] = owner.user_id
        start = begin(client, case.id, content)
        assert start.status_code == 200, start.text
        progress = start.json()
        upload_id = progress["id"]
        assert progress["chunk_count"] == 3
        assert service.get(owner, case.id).status == Status.UPLOADING
        assert begin(client, case.id, content).json()["id"] == upload_id
        assert begin(client, case.id, content, "different-key").json()["id"] == upload_id
        assert begin(client, case.id, content + b" ").status_code == 409
        part = content[:CHUNK]
        assert send(client, case.id, upload_id, 0, part).status_code == 200
        assert send(client, case.id, upload_id, 0, part).json()["received"] == [0]
        pending_path = f"/api/v1/investigations/{case.id}/uploads"
        pending = client.get(pending_path).json()
        assert len(pending) == 1 and pending[0]["received"] == [0]
        assert pending[0]["name"] == "large.json"
        assert send(client, case.id, upload_id, 0, b"x" * CHUNK).status_code == 409
        assert (
            client.post(
                f"/api/v1/investigations/{case.id}/uploads/{upload_id}/complete"
            ).status_code
            == 409
        )
        with pytest.raises(ValueError, match="writes"):
            create_snapshot(config, source[-1] / "unfinished", writers_stopped=True)
        client.headers["X-Development-User"] = "bob"
        assert client.get(pending_path).status_code == 404
        for method, path in [
            ("POST", f"/api/v1/investigations/{case.id}/uploads/{upload_id}/complete"),
            ("PUT", f"/api/v1/investigations/{case.id}/uploads/{upload_id}/parts/1"),
            ("DELETE", f"/api/v1/investigations/{case.id}/uploads/{upload_id}"),
        ]:
            assert (
                client.request(
                    method,
                    path,
                    content=b"private" if method == "PUT" else None,
                    headers={"X-Chunk-SHA256": "0" * 64} if method == "PUT" else None,
                ).status_code
                == 404
            )
        client.headers["X-Development-User"] = owner.user_id
    # A new application instance resumes without any local case file.
    with TestClient(create_app(settings=config)) as reopened:
        reopened.headers["X-Development-User"] = owner.user_id
        assert begin(reopened, case.id, content).json()["received"] == [0]
        for index in [1, 2]:
            assert (
                send(
                    reopened,
                    case.id,
                    upload_id,
                    index,
                    content[index * CHUNK : (index + 1) * CHUNK],
                ).status_code
                == 200
            )
        complete = reopened.post(f"/api/v1/investigations/{case.id}/uploads/{upload_id}/complete")
        assert complete.status_code == 200, complete.text
        artifact = complete.json()
        assert artifact["checksum"] == hashlib.sha256(content).hexdigest()
        assert artifact["size_bytes"] == len(content)
        assert (
            reopened.post(f"/api/v1/investigations/{case.id}/uploads/{upload_id}/complete").json()
            == artifact
        )
        assert begin(reopened, case.id, content).json()["artifact_id"] == artifact["id"]
        assert reopened.get(pending_path).json() == []
        assert service.storage.read(service.artifacts(owner, case.id)[0].storage_key) == content
        with service.database.session() as session:
            assert session.scalar(select(func.count()).select_from(UploadPart)) == 0
            assert session.scalar(select(func.sum(StoredBlob.size_bytes))) == len(content)
        assert (
            DeletionService(service).remove(owner, case.id, case.name)["storage_cleanup"]
            == "complete"
        )
        with service.database.session() as session:
            assert session.scalar(select(func.count()).select_from(UploadSession)) == 0
            assert session.scalar(select(func.count()).select_from(StoredBlob)) == 0


def test_invalid_large_dataset_aborts_atomically_and_expiration_releases_quota(source):
    config, service, owner, case, _, _ = source
    broken = b"{" + b" " * 4_700_000
    with TestClient(create_app(settings=config)) as client:
        client.headers["X-Development-User"] = owner.user_id
        upload_id = begin(client, case.id, broken).json()["id"]
        for index in range(3):
            part = broken[index * CHUNK : (index + 1) * CHUNK]
            assert send(client, case.id, upload_id, index, part).status_code == 200
        assert (
            client.post(
                f"/api/v1/investigations/{case.id}/uploads/{upload_id}/complete"
            ).status_code
            == 422
        )
        assert service.get(owner, case.id).status == Status.CREATED
        with service.database.session() as session:
            assert session.get(UploadSession, upload_id).status == "aborted"
            assert session.scalar(select(func.count()).select_from(UploadPart)) == 0
        second = begin(client, case.id, broken, "second")
        assert second.status_code == 200
        assert send(client, case.id, second.json()["id"], 0, broken[:CHUNK]).status_code == 200
        with service.database.write() as session:
            session.get(UploadSession, second.json()["id"]).expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
        assert service.get(owner, case.id).status == Status.CREATED
        with service.database.session() as session:
            assert session.get(UploadSession, second.json()["id"]).status == "expired"
            assert session.scalar(select(func.count()).select_from(UploadPart)) == 0
        assert begin(client, case.id, broken, "second").status_code == 409


def test_cancel_releases_reserved_case_and_global_staging_quota(source):
    config, service, owner, case, content, _ = source
    second_case = service.create(owner, "Another upload")
    with TestClient(create_app(settings=config)) as client:
        client.headers["X-Development-User"] = owner.user_id
        first = begin(client, case.id, content).json()["id"]
        second = begin(client, second_case.id, content).json()["id"]
        assert send(client, case.id, first, 0, content[:CHUNK]).status_code == 200
        assert send(client, case.id, first, 1, content[CHUNK : 2 * CHUNK]).status_code == 200
        assert send(client, second_case.id, second, 0, content[:CHUNK]).status_code == 200
        # The 6 MB global budget counts partial bytes across investigations.
        refused = send(client, second_case.id, second, 1, content[CHUNK : 2 * CHUNK])
        assert refused.status_code == 429 and refused.json()["error"]["code"] == "QUOTA_EXCEEDED"
        path = f"/api/v1/investigations/{case.id}/uploads/{first}"
        client.headers["X-Development-User"] = "bob"
        assert client.delete(path).status_code == 404
        client.headers["X-Development-User"] = owner.user_id
        assert client.delete(path).json()["status"] == "aborted"
        assert client.delete(path).json()["status"] == "aborted"
        assert service.get(owner, case.id).status == Status.CREATED
        assert client.get(f"/api/v1/investigations/{case.id}/uploads").json() == []
        assert (
            send(client, second_case.id, second, 1, content[CHUNK : 2 * CHUNK]).status_code == 200
        )
        assert send(client, case.id, first, 0, content[:CHUNK]).status_code == 409
        # An ordinary artifact must also respect the bytes reserved by staging.
        assert (
            client.post(
                f"/api/v1/investigations/{case.id}/artifacts",
                content=content,
                headers={"Content-Type": "application/json"},
            ).status_code
            == 429
        )


def test_session_history_has_case_and_global_admission_limits(source):
    config, service, owner, case, content, _ = source
    config.max_upload_sessions_per_investigation = 1
    config.max_upload_sessions_total = 2
    second = service.create(owner, "Second")
    third = service.create(owner, "Third")
    with TestClient(create_app(settings=config)) as client:
        client.headers["X-Development-User"] = owner.user_id
        upload = begin(client, case.id, content).json()
        assert begin(client, case.id, content, "resume").json()["id"] == upload["id"]
        assert (
            client.delete(f"/api/v1/investigations/{case.id}/uploads/{upload['id']}").status_code
            == 200
        )
        assert begin(client, case.id, content, "new").status_code == 429
        active = begin(client, second.id, content)
        assert active.status_code == 200
        assert begin(client, third.id, content).status_code == 429
        assert begin(client, second.id, content, "retry").json()["id"] == active.json()["id"]


def test_fragment_http_bounds_and_integrity_fail_without_accepting_partial_bytes(source):
    config, _, owner, case, content, _ = source
    with TestClient(create_app(settings=config)) as client:
        client.headers["X-Development-User"] = owner.user_id
        root = f"/api/v1/investigations/{case.id}/uploads"
        invalid_size = client.post(
            root,
            json={
                "name": "source.json",
                "size_bytes": True,
                "checksum": hashlib.sha256(content).hexdigest(),
            },
            headers={"Idempotency-Key": "bad-size"},
        )
        assert invalid_size.status_code == 422
        upload = begin(client, case.id, content).json()["id"]
        path = f"{root}/{upload}/parts/0"
        assert (
            client.put(
                path, content=content[:CHUNK], headers={"X-Chunk-SHA256": "0" * 64}
            ).status_code
            == 422
        )
        assert send(client, case.id, upload, 0, content[: CHUNK - 1]).status_code == 422
        assert send(client, case.id, upload, 0, content[: CHUNK + 1]).status_code == 413
        assert client.get(root).json()[0]["received"] == []
        # A false short content-length cannot bypass counting actual streamed bytes.
        assert (
            client.put(
                path,
                content=content[: CHUNK + 1],
                headers={
                    "X-Chunk-SHA256": hashlib.sha256(content[: CHUNK + 1]).hexdigest(),
                    "Content-Length": "1",
                },
            ).status_code
            == 413
        )
        assert client.get(root).json()[0]["received"] == []
        assert send(client, case.id, upload, 0, content[:CHUNK]).status_code == 200
