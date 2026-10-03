"""Independent invocations share durable bytes, admission, claims and erasure."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    EventFeatureRow,
    FeatureTable,
)
from ringsentinel.models.artifact import write_artifact
from ringsentinel.models.tabular import BoostedTreeDetector
from ringsentinel.platform.backup import create_snapshot, restore_snapshot
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import DatabaseStorageBackend, import_local, storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import AnalysisRun, Status, StoredBlob
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


@pytest.fixture
def config(tmp_path):
    features = TRANSACTION_FEATURES + NETWORK_FEATURES
    table = FeatureTable(
        tuple(
            EventFeatureRow(str(i), datetime.now(UTC), {name: float(i % 7) for name in features})
            for i in range(60)
        )
    )
    model = BoostedTreeDetector(features, random_state=105)
    model.fit((table,), (np.array([i % 2 for i in range(60)]),))
    path = tmp_path / "unit-trusted-model.joblib"
    metadata = write_artifact(model, 0.5, path)
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'db'}",
        storage_root=tmp_path / "disposable-scratch",
        storage_backend="database",
        execution_mode="request",
        analysis_timeout_seconds=60,
        model_artifact_path=path,
        model_artifact_sha256=metadata["sha256"],
    )


@pytest.fixture
def service(config):
    db = Database(config.database_url.get_secret_value())
    db.migrate()
    yield InvestigationService(db, storage_for(db, config), config)
    db.engine.dispose()


def saved_run(service, owner="alice", key="first"):
    principal = Principal(owner)
    case = service.create(principal, "Durable case")
    content = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    artifact = service.attach(principal, case.id, content, "input.json", "application/json")
    run = service.start(principal, case.id, artifact.id, key)
    return principal, case, artifact, run


def test_independent_storage_quota_and_integrity(service):
    url = service.settings.database_url.get_secret_value()

    def write():
        db = Database(url)
        try:
            return DatabaseStorageBackend(db, 8).save(b"123456").key
        except ProductError as error:
            return error.code
        finally:
            db.engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: write(), range(2)))
    assert outcomes.count("QUOTA_EXCEEDED") == 1
    key = next(value for value in outcomes if value != "QUOTA_EXCEEDED")
    assert service.storage.read(key) == b"123456"
    with service.database.write() as session:
        obj = session.get(StoredBlob, key)
        obj.content = b"bad"
    with pytest.raises(ProductError, match="could not"):
        service.storage.read(key)
    for key in ["../secret", "https://outside.example/secret", ""]:
        with pytest.raises(ValueError):
            service.storage.read(key)


def test_metadata_failure_rolls_back_bytes_and_quota(service, monkeypatch):
    principal = Principal("alice")
    case = service.create(principal, "Rollback")
    content = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    original = service.storage.save_in

    def fail_after_bytes(session, payload):
        original(session, payload)
        raise RuntimeError("injected metadata failure")

    monkeypatch.setattr(service.storage, "save_in", fail_after_bytes)
    with pytest.raises(RuntimeError):
        service.attach(principal, case.id, content, "x.json", "application/json")
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(StoredBlob)) == 0
    assert service.get(principal, case.id).status == Status.CREATED
    assert service.artifacts(principal, case.id) == []


def test_claims_are_scoped_and_serialize_across_instances(service):
    alice, _, _, first = saved_run(service)
    bob, _, _, second = saved_run(service, "bob")
    assert service.claim(second.id, alice) is None
    db = Database(service.settings.database_url.get_secret_value())
    other = InvestigationService(db, storage_for(db, service.settings), service.settings)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [
                pool.submit(service.claim, first.id, alice),
                pool.submit(other.claim, second.id, bob),
            ]
            claims = [task.result() for task in tasks]
        assert sum(value is not None for value in claims) == 1
        claimed = next(value for value in claims if value)
        assert service.expire_deadlines() == 0
        service.finish(claimed, {"rings": []})
        pending, owner = (second, bob) if claimed == first.id else (first, alice)
        assert other.claim(pending.id, owner) == pending.id
    finally:
        db.engine.dispose()


def test_interrupted_invocation_is_fenced_and_does_not_fail_a_healthy_job(service):
    owner, _, _, run = saved_run(service)
    assert service.claim(run.id, owner) == run.id
    assert service.expire_deadlines() == 0
    with service.database.write() as session:
        session.get(AnalysisRun, run.id).execution_deadline = datetime.now(UTC) - timedelta(
            seconds=1
        )
    assert service.expire_deadlines() == 1
    record = service.run(owner, run.id)
    assert record.status == Status.FAILED and record.error_code == "WORKER_INTERRUPTED"
    assert record.active_slot is None and record.executor_slot is None
    with pytest.raises(ProductError):
        service.finish(run.id, {"secret": "late result"})
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(StoredBlob)) == 1  # input only


def test_late_completion_and_unclaimed_queue_expiration(service):
    owner, _, _, first = saved_run(service)
    service.claim(first.id, owner)
    with service.database.write() as session:
        session.get(AnalysisRun, first.id).execution_deadline = datetime.now(UTC) - timedelta(
            seconds=1
        )
    service.finish(first.id, {"secret": "late result"})
    assert service.run(owner, first.id).error_code == "ANALYSIS_TIMEOUT"
    owner, _, _, second = saved_run(service, key="second")
    with service.database.write() as session:
        session.get(AnalysisRun, second.id).execution_deadline = datetime.now(UTC) - timedelta(
            seconds=1
        )
    assert service.run(owner, second.id).error_code == "QUEUE_EXPIRED"


@pytest.mark.parametrize("read", ["get", "list", "runs"])
def test_case_reads_recover_only_the_owners_expired_work(service, read):
    owner, case, _, run = saved_run(service)
    _, _, _, hidden = saved_run(service, "bob")
    with service.database.write() as session:
        for run_id in [run.id, hidden.id]:
            session.get(AnalysisRun, run_id).execution_deadline = datetime.now(UTC) - timedelta(
                seconds=1
            )
    method = getattr(service, read)
    method(owner) if read == "list" else method(owner, case.id)
    recovered = service.get(owner, case.id)
    assert recovered.status == Status.FAILED
    assert recovered.updated_at != case.updated_at
    assert service.run(owner, run.id).error_code == "QUEUE_EXPIRED"
    with service.database.session() as session:
        assert session.get(AnalysisRun, hidden.id).status == Status.QUEUED


def test_start_releases_an_expired_case_without_requiring_a_previous_status_read(service):
    owner, case, artifact, first = saved_run(service)
    with service.database.write() as session:
        session.get(AnalysisRun, first.id).execution_deadline = datetime.now(UTC) - timedelta(
            seconds=1
        )
    second = service.start(owner, case.id, artifact.id, "explicit-retry")
    assert second.status == Status.QUEUED and second.id != first.id
    assert service.run(owner, first.id).error_code == "QUEUE_EXPIRED"
    assert service.get(owner, case.id).status == Status.QUEUED


def test_real_request_scoped_worker_retry_restart_owner_and_erasure(service, config, monkeypatch):
    owner, case, artifact, run = saved_run(service)
    # A deployment/cold start must not recover a healthy invocation or start a daemon.
    with TestClient(create_app(settings=config)) as client:
        assert client.app.state.executor.thread is None
        assert client.get("/api/v1/ready").status_code == 200
        denied = client.post(
            f"/api/v1/runs/{run.id}/execute", headers={"X-Development-User": "bob"}
        )
        assert denied.status_code == 404
        response = client.post(
            f"/api/v1/runs/{run.id}/execute", headers={"X-Development-User": owner.user_id}
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
        assert (
            response.json()["version_metadata"]["model_artifact_sha256"]
            == config.model_artifact_sha256
        )
        assert (
            client.post(
                f"/api/v1/runs/{run.id}/execute", headers={"X-Development-User": owner.user_id}
            ).json()
            == response.json()
        )
    # Fresh engine and app, no local case files or model retraining.
    assert not list(config.storage_root.glob("*.json"))
    db = Database(config.database_url.get_secret_value())
    reopened = InvestigationService(db, storage_for(db, config), config)
    try:
        result = reopened.result(owner, run.id)
        assert result["event_count"] == len(
            json.loads(reopened.storage.read(artifact.storage_key))["events"]
        )
        assert (
            hashlib.sha256(reopened.storage.read(artifact.storage_key)).hexdigest()
            == artifact.checksum
        )
        original = reopened.storage.delete_in

        def fail_after_delete(session, key):
            original(session, key)
            raise RuntimeError("injected interruption")

        with monkeypatch.context() as patch:
            patch.setattr(reopened.storage, "delete_in", fail_after_delete)
            with pytest.raises(RuntimeError):
                DeletionService(reopened).remove(owner, case.id, case.name)
        assert reopened.result(owner, run.id) == result
        assert (
            DeletionService(reopened).remove(owner, case.id, case.name)["storage_cleanup"]
            == "complete"
        )
        with db.session() as session:
            assert session.scalar(select(func.count()).select_from(StoredBlob)) == 0
        with pytest.raises(ProductError):
            reopened.result(owner, run.id)
    finally:
        db.engine.dispose()


def test_database_objects_survive_verified_offline_snapshot(service, config, tmp_path):
    owner, case, artifact, run = saved_run(service)
    service.claim(run.id, owner)
    service.finish(run.id, {"rings": [], "test": "persisted bytes"})
    snapshot = tmp_path / "snapshot"
    manifest = create_snapshot(config, snapshot, writers_stopped=True)
    assert manifest["storage_backend"] == "database"
    assert not list((snapshot / "objects").iterdir())
    restored_config = config.model_copy(
        update={
            "database_url": config.database_url.__class__(f"sqlite:///{tmp_path / 'restored.db'}"),
            "storage_root": tmp_path / "restored-scratch",
        }
    )
    restore_snapshot(restored_config, snapshot, writers_stopped=True)
    db = Database(restored_config.database_url.get_secret_value())
    try:
        reopened = InvestigationService(db, storage_for(db, restored_config), restored_config)
        assert reopened.result(owner, run.id) == {"rings": [], "test": "persisted bytes"}
        assert reopened.artifacts(owner, case.id)[0].checksum == artifact.checksum
    finally:
        db.engine.dispose()


def test_request_configuration_rejects_ephemeral_storage_and_unbounded_runtime():
    with pytest.raises(ValueError, match="durable"):
        Settings(execution_mode="request", analysis_timeout_seconds=60)
    with pytest.raises(ValueError, match="timeout"):
        Settings(execution_mode="request", storage_backend="database", analysis_timeout_seconds=300)
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(
            environment="production",
            execution_mode="request",
            storage_backend="database",
            analysis_timeout_seconds=60,
        )


def test_import_existing_files_preserves_keys_and_rejects_unverified_state(service, config):
    local = InvestigationService(service.database, LocalStorageBackend(config.storage_root), config)
    owner, case, artifact, run = saved_run(local)
    local.claim(run.id, owner)
    local.finish(run.id, {"rings": [], "original": "persisted"})
    assert not service.storage.ready()
    with pytest.raises(ValueError):
        import_local(config)
    original_input = config.storage_root / artifact.storage_key
    original_bytes = original_input.read_bytes()
    original_input.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        import_local(config, writers_stopped=True)
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(StoredBlob)) == 0
    original_input.write_bytes(original_bytes)
    assert import_local(config, writers_stopped=True) == {
        "copied": 2,
        "source_objects_removed": False,
    }
    assert service.storage.ready()
    assert import_local(config, writers_stopped=True)["copied"] == 0
    assert service.artifacts(owner, case.id)[0].storage_key == artifact.storage_key
    assert service.result(owner, run.id) == {"rings": [], "original": "persisted"}
    assert original_input.read_bytes() == original_bytes
