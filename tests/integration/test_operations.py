"""Operator counts detect stalled work without changing saved lifecycle records."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.database import Database
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.models import AnalysisRun, Status, StorageDeletion, utcnow
from ringsentinel.platform.operations import report
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


@pytest.fixture
def queued(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'db'}")
    database.migrate()
    settings = Settings(storage_root=tmp_path / "objects", jobs_enabled=False)
    service = InvestigationService(database, LocalStorageBackend(settings.storage_root), settings)
    owner = Principal("private-owner-fixture")
    case = service.create(owner, "private-case-fixture")
    payload = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    artifact = service.attach(owner, case.id, payload, "private-input.json", "application/json")
    run = service.start(owner, case.id, artifact.id, "private-idempotency")
    yield service, owner, case, artifact, run
    database.engine.dispose()


def test_report_detects_overdue_work_and_retains_private_records(queued):
    service, owner, case, artifact, run = queued
    database = service.database
    try:
        assert report(database)["status"] == "ok"
        with database.session.begin() as session:
            saved = session.get(AnalysisRun, run.id)
            saved.execution_deadline = utcnow() - timedelta(minutes=1)
        result = report(database)
        assert result["alerts"] == ["EXECUTION_DEADLINE_EXCEEDED"]
        assert result["overdue_runs"] == 1
        assert result["run_counts"]["queued"] == 1
        assert not result["automatic_recovery"]
        assert all(
            secret not in str(result)
            for secret in (case.id, run.id, owner.user_id, case.name, artifact.original_name)
        )
        with database.session() as session:
            assert session.scalar(select(AnalysisRun.status)) == Status.QUEUED
    finally:
        database.engine.dispose()


def test_queue_wait_threshold_detects_legacy_deadlineless_work_without_mutating(
    queued, monkeypatch
):
    from ringsentinel.platform import operations

    service, owner, case, artifact, run = queued
    database = service.database
    now = utcnow()
    monkeypatch.setattr(operations, "utcnow", lambda: now)
    with database.session.begin() as session:
        saved = session.get(AnalysisRun, run.id)
        saved.created_at = now - timedelta(minutes=30)
    boundary = report(database)
    assert boundary["queued_wait_exceeded"] == 0
    assert boundary["oldest_queued_seconds"] == 1800
    with database.session.begin() as session:
        session.get(AnalysisRun, run.id).created_at = now - timedelta(minutes=30, seconds=1)
    result = report(database)
    assert result["alerts"] == ["QUEUE_WAIT_EXCEEDED"]
    assert result["queued_wait_exceeded"] == 1 and result["overdue_runs"] == 0
    assert result["oldest_queued_seconds"] == 1801
    assert report(database, queue_wait_minutes=31)["status"] == "ok"
    with database.session() as session:
        saved = session.get(AnalysisRun, run.id)
        assert saved.status == Status.QUEUED and saved.execution_deadline is None
        assert saved.active_slot == case.id and saved.error_code is None
    assert all(
        secret not in str(result)
        for secret in (
            owner.user_id,
            case.id,
            case.name,
            run.id,
            artifact.original_name,
            artifact.storage_key,
        )
    )
    assert service.claim() == run.id
    # An old creation time must not keep alerting once the job starts or finishes.
    assert report(database)["queued_wait_exceeded"] == 0
    assert report(database)["oldest_queued_seconds"] is None
    service.finish(run.id, {"rings": [], "verification": "generated-lifecycle-fixture"})
    assert report(database)["status"] == "ok"


def test_delayed_erasure_cleanup_alert_clears_only_after_real_cleanup(queued, monkeypatch):
    from ringsentinel.platform import operations

    service, owner, case, artifact, run = queued
    database = service.database
    assert service.claim() == run.id
    service.finish(run.id, {"rings": [], "verification": "generated-lifecycle-fixture"})
    original_delete = service.storage.delete

    def unavailable(*_):
        raise OSError("private-path-must-not-leak")

    monkeypatch.setattr(service.storage, "delete", unavailable)
    assert (
        DeletionService(service).remove(owner, case.id, case.name)["storage_cleanup"] == "pending"
    )
    now = utcnow()
    monkeypatch.setattr(operations, "utcnow", lambda: now)
    with database.session.begin() as session:
        for task in session.scalars(select(StorageDeletion)):
            task.created_at = now - timedelta(minutes=30, seconds=1)
    result = report(database)
    assert result["alerts"] == ["STORAGE_CLEANUP_OVERDUE"]
    assert result["storage_cleanup_overdue"] == result["pending_storage_deletions"] == 2
    assert result["oldest_pending_deletion_seconds"] == 1801
    assert report(database, cleanup_wait_minutes=31)["status"] == "ok"
    assert service.storage.exists(artifact.storage_key)
    with database.session() as session:
        assert [task.attempts for task in session.scalars(select(StorageDeletion))] == [1, 1]
    assert all(
        secret not in str(result)
        for secret in (
            case.id,
            run.id,
            artifact.storage_key,
            owner.user_id,
            "private-path-must-not-leak",
        )
    )
    monkeypatch.setattr(service.storage, "delete", original_delete)
    assert DeletionService(service).cleanup()["pending"] == 0
    assert not service.storage.exists(artifact.storage_key)
    result = report(database)
    assert result["status"] == "ok" and result["pending_storage_deletions"] == 0
    assert result["oldest_pending_deletion_seconds"] is None


@pytest.mark.parametrize("value", [0, 1441, True, 1.5])
def test_report_rejects_invalid_threshold_without_creating_database(tmp_path, value):
    path = tmp_path / "not-created.db"
    database = Database(f"sqlite:///{path}")
    try:
        with pytest.raises(ValueError, match="whole minutes"):
            report(database, queue_wait_minutes=value)
        with pytest.raises(ValueError, match="whole minutes"):
            report(database, cleanup_wait_minutes=value)
        assert not path.exists()
    finally:
        database.engine.dispose()


def test_report_does_not_create_missing_sqlite_database(tmp_path):
    path = tmp_path / "not-created.db"
    database = Database(f"sqlite:///{path}")
    try:
        with pytest.raises(ValueError, match="existing migrated"):
            report(database)
        assert not path.exists()
    finally:
        database.engine.dispose()
