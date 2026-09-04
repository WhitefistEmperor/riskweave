from concurrent.futures import ThreadPoolExecutor

import pytest

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.database import Database
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.jobs import LocalJobExecutor
from ringsentinel.platform.locking import FileLock
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
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    yield InvestigationService(db, LocalStorageBackend(settings.storage_root), settings)
    db.engine.dispose()


@pytest.fixture(scope="module")
def payload():
    return (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )


def test_owner_total_and_concurrent_creation_quotas(service):
    service.settings.max_investigations_per_owner = 1
    service.settings.max_investigations_total = 2

    def create(_):
        try:
            return service.create(Principal("alice"), "Review")
        except ProductError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(create, range(2)))
    assert sum(isinstance(x, ProductError) for x in outcomes) == 1
    service.create(Principal("bob"), "Other")
    with pytest.raises(ProductError, match="operational limit"):
        service.create(Principal("carol"), "Full")


def test_artifact_run_pending_limits_preserve_idempotency(service, payload):
    p = Principal("alice")
    inv = service.create(p, "Review")
    service.settings.max_artifacts_per_investigation = 1
    service.settings.max_runs_per_investigation = 1
    service.settings.max_pending_runs = 1
    artifact = service.attach(p, inv.id, payload, "x.json", "application/json")
    assert service.attach(p, inv.id, payload, "x.json", "application/json").id == artifact.id
    with pytest.raises(ProductError, match="operational limit"):
        service.attach(p, inv.id, payload + b" ", "x.json", "application/json")
    run = service.start(p, inv.id, artifact.id, "key")
    assert service.start(p, inv.id, artifact.id, "key").id == run.id
    other = service.create(p, "Other")
    obj = service.attach(p, other.id, payload, "x.json", "application/json")
    with pytest.raises(ProductError, match="operational limit"):
        service.start(p, other.id, obj.id, "other")
    service.claim()
    service.finish(run.id, {"rings": []})
    assert service.start(p, inv.id, artifact.id, "key").id == run.id
    with pytest.raises(ProductError, match="operational limit"):
        service.start(p, inv.id, artifact.id, "new")


def test_storage_budget_counts_orphans_and_never_deletes(service):
    storage = LocalStorageBackend(service.settings.storage_root, limit_bytes=10)
    first = storage.save(b"12345678")
    with pytest.raises(ProductError, match="operational limit"):
        storage.save(b"123")
    assert storage.read(first.key) == b"12345678"
    assert len(list(storage.root.glob("*.json"))) == 1
    assert storage.ready()  # Temporary two-byte readiness object fits and is removed.
    with FileLock(storage.root / ".write.lock"), pytest.raises(ProductError):
        storage.save(b"1")


def test_result_size_limit_preserves_running_record_until_safe_failure(service, payload):
    p = Principal("alice")
    inv = service.create(p, "Review")
    artifact = service.attach(p, inv.id, payload, "x.json", "application/json")
    run = service.start(p, inv.id, artifact.id, "key")
    service.claim()
    service.settings.result_limit_bytes = 1024
    with pytest.raises(ProductError):
        service.finish(run.id, {"huge": "a" * 2000})
    assert service.run(p, run.id).result_reference is None
    service.finish(run.id, error_code="QUOTA_EXCEEDED")
    assert service.run(p, run.id).error_code == "QUOTA_EXCEEDED"


def test_exclusive_scheduler_and_orphan_startup_guard(service):
    first = LocalJobExecutor(service)
    second = LocalJobExecutor(service)
    first.start()
    try:
        with pytest.raises(RuntimeError, match="ownership"):
            second.start()
        with pytest.raises(RuntimeError, match="already started"):
            first.start()
    finally:
        first.stop()
    # OS lock release permits a later process; stale files are not stale ownership.
    with FileLock(service.settings.storage_root / ".analysis.lock"), pytest.raises(RuntimeError):
        LocalJobExecutor(service).start()
    replacement = LocalJobExecutor(service)
    replacement.start()
    replacement.stop()
    assert not replacement.thread.is_alive()
