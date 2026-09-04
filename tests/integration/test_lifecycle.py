import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.database import Database
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import Status
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


@pytest.fixture
def service(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'db'}",
        storage_root=tmp_path / "objects",
        jobs_enabled=False,
    )
    database = Database(settings.database_url.get_secret_value())
    database.migrate()
    yield InvestigationService(database, LocalStorageBackend(settings.storage_root), settings)
    database.engine.dispose()


@pytest.fixture
def dataset_bytes():
    return (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )


def test_storage_safety(tmp_path):
    storage = LocalStorageBackend(tmp_path / "objects")
    assert storage.ready()
    obj = storage.save(b"{}")
    assert storage.read(obj.key) == b"{}"
    assert storage.exists(obj.key)
    assert storage.reference(obj.key) == f"object:{obj.key}"
    for bad in ["../secret", "C:\\secret", "/etc/passwd", "a/../b.json", ""]:
        with pytest.raises(ValueError):
            storage.read(bad)
    storage.delete(obj.key)
    with pytest.raises(FileNotFoundError):
        storage.read(obj.key)


def test_owner_lifecycle_idempotency_and_reopen(service, dataset_bytes):
    alice, bob = Principal("alice"), Principal("bob")
    inv = service.create(alice, "Review")
    assert service.list(bob) == []
    with pytest.raises(ProductError, match="Resource not found"):
        service.get(bob, inv.id)
    artifact = service.attach(alice, inv.id, dataset_bytes, "../input.json", "application/json")
    assert artifact.original_name == "input.json"
    assert (
        service.attach(alice, inv.id, dataset_bytes, "again.json", "application/json").id
        == artifact.id
    )
    run = service.start(alice, inv.id, artifact.id, "request1")
    assert run.status == Status.QUEUED
    assert service.start(alice, inv.id, artifact.id, "request1").id == run.id
    with pytest.raises(ProductError):
        service.start(alice, inv.id, artifact.id, "request2")
    with pytest.raises(ProductError):
        service.run(bob, run.id)
    with pytest.raises(ProductError):
        service.result(alice, run.id)
    assert service.claim() == run.id
    assert service.run(alice, run.id).status == Status.RUNNING
    assert service.claim() is None
    service.finish(run.id, {"rings": []})
    assert service.run(alice, run.id).status == Status.COMPLETED
    reopened = InvestigationService(service.database, service.storage, service.settings)
    assert reopened.result(alice, run.id) == {"rings": []}
    retry = service.start(alice, inv.id, artifact.id, "request2")
    service.claim()
    service.finish(retry.id, error_code="ANALYSIS_FAILED")
    assert service.run(alice, retry.id).status == Status.FAILED
    assert service.get(alice, inv.id).status == Status.FAILED


def test_invalid_upload_and_recovery(service, dataset_bytes):
    principal = Principal("alice")
    inv = service.create(principal, "Review")
    for payload, kind in [(b"{}", "application/json"), (dataset_bytes, "text/csv")]:
        with pytest.raises(ProductError, match="DatasetBundle"):
            service.attach(principal, inv.id, payload, "file", kind)
    assert service.get(principal, inv.id).status == Status.CREATED
    artifact = service.attach(principal, inv.id, dataset_bytes, "x.json", "application/json")
    run = service.start(principal, inv.id, artifact.id, "key")
    service.claim()
    service.recover_interrupted()
    assert service.run(principal, run.id).error_code == "WORKER_INTERRUPTED"


def test_real_analysis_subprocess_and_timeout(service, dataset_bytes, monkeypatch):
    from ringsentinel.platform.jobs import LocalJobExecutor

    actual_popen = subprocess.Popen
    children = []

    def launch(*args, **kwargs):
        # Observe the REAL OS processes; do not substitute execution or detector output.
        process = actual_popen(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr("ringsentinel.platform.jobs.subprocess.Popen", launch)
    principal = Principal("alice")
    inv = service.create(principal, "Execution")
    artifact = service.attach(principal, inv.id, dataset_bytes, "x.json", "application/json")
    run = service.start(principal, inv.id, artifact.id, "real")
    assert service.claim() == run.id
    LocalJobExecutor(service).execute(run.id)
    assert children[-1].poll() == 0
    assert service.run(principal, run.id).status == Status.COMPLETED
    assert service.result(principal, run.id)["event_count"] > 0
    run2 = service.start(principal, inv.id, artifact.id, "timeout")
    assert service.claim() == run2.id
    service.settings.analysis_timeout_seconds = 1
    LocalJobExecutor(service).execute(run2.id)
    assert service.run(principal, run2.id).error_code == "ANALYSIS_TIMEOUT"
    assert children[-1].poll() is not None
    assert children[-1].returncode != 0
    assert service.run(principal, run2.id).result_reference is None


def test_storage_collision_never_removes_existing_object(tmp_path, monkeypatch):
    monkeypatch.setattr("ringsentinel.platform.storage.uuid4", lambda: UUID(int=1))
    storage = LocalStorageBackend(tmp_path)
    first = storage.save(b"original")
    with pytest.raises(FileExistsError):
        storage.save(b"replacement")
    assert storage.read(first.key) == b"original"


def test_upload_limits_and_malformed_progression(service, dataset_bytes):
    principal = Principal("alice")
    inv = service.create(principal, "Bad input")
    malformed = json.loads(dataset_bytes)
    malformed["fraud_rings"][0]["attack_progression"] = []
    with pytest.raises(ProductError) as exc:
        service.attach(principal, inv.id, json.dumps(malformed).encode(), "x", "application/json")
    assert exc.value.code == "INVALID_DATASET"
    service.settings.upload_limit_bytes = 1024
    with pytest.raises(ProductError) as exc:
        service.attach(principal, inv.id, dataset_bytes, "x", "application/json")
    assert exc.value.code == "UPLOAD_TOO_LARGE"
    assert service.artifacts(principal, inv.id) == []


def test_concurrent_start_and_result_integrity(service, dataset_bytes):
    principal = Principal("alice")
    inv = service.create(principal, "Concurrency")
    artifact = service.attach(principal, inv.id, dataset_bytes, "x", "application/json")

    def start(key):
        try:
            return service.start(principal, inv.id, artifact.id, key)
        except ProductError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(start, ["first", "second"]))
    assert sum(isinstance(item, ProductError) for item in outcomes) == 1
    assert len(service.runs(principal, inv.id)) == 1
    run_id = service.claim()
    service.finish(run_id, {"rings": []})
    service.database.engine.dispose()
    reopened_db = Database(service.settings.database_url.get_secret_value())
    reopened = InvestigationService(reopened_db, service.storage, service.settings)
    try:
        assert reopened.result(principal, run_id) == {"rings": []}
        run = reopened.run(principal, run_id)
        service.storage._path(run.result_reference).write_bytes(b'{"rings": ["tampered"]}')
        with pytest.raises(ProductError) as exc:
            reopened.result(principal, run_id)
        assert exc.value.code == "INTERNAL_ERROR"
    finally:
        reopened_db.engine.dispose()


def test_real_worker_failure_and_shutdown(service, dataset_bytes):
    from ringsentinel.platform.jobs import LocalJobExecutor

    principal = Principal("alice")
    inv = service.create(principal, "Worker failure")
    artifact = service.attach(principal, inv.id, dataset_bytes, "x", "application/json")
    run = service.start(principal, inv.id, artifact.id, "corrupt")
    service.claim()
    service.storage._path(artifact.storage_key).write_bytes(b"corrupt")
    LocalJobExecutor(service).execute(run.id)
    assert service.run(principal, run.id).error_code == "ANALYSIS_FAILED"
    retry = service.start(principal, inv.id, artifact.id, "shutdown")
    service.claim()
    executor = LocalJobExecutor(service)
    executor.stopping.set()
    executor.execute(retry.id)
    assert service.run(principal, retry.id).error_code == "WORKER_INTERRUPTED"
