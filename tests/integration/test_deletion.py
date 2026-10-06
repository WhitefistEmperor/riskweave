"""Deletion must preserve ownership, live work and retryable cleanup after failures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform.backup import apply_retention, create_snapshot, retention_report
from ringsentinel.platform.database import Database
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.locking import FileLock
from ringsentinel.platform.models import (
    AnalysisRun,
    CandidateReview,
    Investigation,
    ReviewAudit,
    ReviewDisposition,
    Status,
    StorageDeletion,
)
from ringsentinel.platform.reviews import ReviewService
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


@pytest.fixture
def saved(tmp_path):
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'deletion.db'}",
        storage_root=tmp_path / "objects",
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    service = InvestigationService(db, LocalStorageBackend(settings.storage_root), settings)
    owner = Principal("deletion-owner")
    inv = service.create(owner, "Delete this case")
    payload = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    artifact = service.attach(owner, inv.id, payload, "input.json", "application/json")
    run = service.start(owner, inv.id, artifact.id, "first")
    service.claim()
    # Persisted transport fixture only; real detector behavior is covered by smoke/browser tests.
    service.finish(run.id, {"rings": [{"candidate": {"candidate_id": "candidate"}}]})
    ReviewService(service).save(
        owner,
        run.id,
        "candidate",
        ReviewDisposition.INVESTIGATING,
        "Investigate shared devices.",
        0,
        "first-review",
    )
    yield service, owner, inv, artifact, run.id, payload
    db.engine.dispose()


def test_http_erasure_removes_case_reviews_and_files_without_touching_another_owner(saved):
    service, owner, inv, artifact, run_id, payload = saved
    other = Principal("other-owner")
    other_case = service.create(other, "Keep this case")
    other_artifact = service.attach(other, other_case.id, payload, "same.json", "application/json")
    result_key = service.run(owner, run_id).result_reference
    path = f"/api/v1/investigations/{inv.id}"
    updated = service.get(owner, inv.id).updated_at.replace(tzinfo=UTC).isoformat()
    with TestClient(create_app(settings=service.settings)) as client:
        assert (
            client.request(
                "DELETE", path, json={"confirm_name": inv.name, "expected_updated_at": updated}
            ).status_code
            == 404
        )
        client.headers["X-Development-User"] = owner.user_id
        assert (
            client.request(
                "DELETE", path, json={"confirm_name": "Wrong", "expected_updated_at": updated}
            ).status_code
            == 409
        )
        assert client.request("DELETE", path, json={}).status_code == 422
        assert service.storage.exists(artifact.storage_key)
        response = client.request(
            "DELETE", path, json={"confirm_name": inv.name, "expected_updated_at": updated}
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "investigation_id": inv.id,
            "status": "deleted",
            "storage_cleanup": "complete",
        }
        for target in [
            path,
            path + "/artifacts",
            path + "/runs",
            f"/api/v1/runs/{run_id}",
            f"/api/v1/runs/{run_id}/results",
            f"/api/v1/runs/{run_id}/rings/candidate/review",
        ]:
            assert client.get(target).status_code == 404
        assert (
            client.request(
                "DELETE", path, json={"confirm_name": inv.name, "expected_updated_at": updated}
            ).status_code
            == 404
        )
    assert not service.storage.exists(artifact.storage_key)
    assert not service.storage.exists(result_key)
    assert service.storage.read(other_artifact.storage_key) == payload
    assert service.get(other, other_case.id).name == "Keep this case"
    with service.database.session() as session:
        for model in (AnalysisRun, CandidateReview, ReviewAudit, StorageDeletion):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("state", [Status.QUEUED, Status.RUNNING, Status.UPLOADING])
def test_active_work_blocks_erasure_and_preserves_bytes(saved, state):
    service, owner, inv, artifact, run_id, _ = saved
    with service.database.session.begin() as session:
        session.execute(
            update(Investigation).where(Investigation.id == inv.id).values(status=state)
        )
    with pytest.raises(ProductError) as failure:
        DeletionService(service).remove(owner, inv.id, inv.name)
    assert failure.value.code == "CONFLICT"
    assert service.storage.exists(artifact.storage_key)
    assert service.run(owner, run_id).status == Status.COMPLETED
    # A stale parent status still must not bypass an active run.
    with service.database.session.begin() as session:
        session.execute(
            update(Investigation).where(Investigation.id == inv.id).values(status=Status.COMPLETED)
        )
        session.execute(
            update(AnalysisRun).where(AnalysisRun.id == run_id).values(status=Status.QUEUED)
        )
    with pytest.raises(ProductError):
        DeletionService(service).remove(owner, inv.id, inv.name)


def test_cleanup_failure_survives_reopen_and_prevents_new_backups(saved, tmp_path, monkeypatch):
    service, owner, inv, artifact, run_id, _ = saved
    result_key = service.run(owner, run_id).result_reference
    actual_delete = service.storage.delete

    def unavailable(key):
        raise PermissionError("Private operator detail must not appear in output")

    monkeypatch.setattr(service.storage, "delete", unavailable)
    result = DeletionService(service).remove(owner, inv.id, inv.name)
    assert result["storage_cleanup"] == "pending"
    assert service.list(owner) == []
    with service.database.session() as session:
        tasks = list(session.scalars(select(StorageDeletion)))
        assert {task.key for task in tasks} == {artifact.storage_key, result_key}
        assert all(
            task.attempts == 1 and task.last_error_code == "STORAGE_UNAVAILABLE" for task in tasks
        )
    with pytest.raises(ValueError, match="pending storage deletion"):
        create_snapshot(service.settings, tmp_path / "blocked-snapshot", writers_stopped=True)
    assert not (tmp_path / "blocked-snapshot").exists()
    monkeypatch.setattr(service.storage, "delete", actual_delete)
    reopened_db = Database(service.settings.database_url.get_secret_value())
    try:
        reopened = InvestigationService(
            reopened_db, LocalStorageBackend(service.settings.storage_root), service.settings
        )
        assert DeletionService(reopened).cleanup() == {"removed": 2, "pending": 0}
        assert DeletionService(reopened).cleanup() == {"removed": 0, "pending": 0}
        assert not reopened.storage.exists(artifact.storage_key)
        assert not reopened.storage.exists(result_key)
    finally:
        reopened_db.engine.dispose()
    assert (
        len(
            create_snapshot(service.settings, tmp_path / "clean-snapshot", writers_stopped=True)[
                "files"
            ]
        )
        == 1
    )


def test_cleanup_is_idempotent_after_unlink_without_ack_and_never_deletes_live_references(saved):
    service, _, _, artifact, _, _ = saved
    missing = "a" * 32 + ".json"
    with service.database.session.begin() as session:
        session.add(StorageDeletion(key=missing))
        session.add(StorageDeletion(key=artifact.storage_key))
    assert DeletionService(service).cleanup() == {"removed": 1, "pending": 1}
    assert service.storage.exists(artifact.storage_key)
    with service.database.session() as session:
        assert (
            session.get(StorageDeletion, artifact.storage_key).last_error_code
            == "REFERENCED_OBJECT"
        )


def test_transaction_failure_never_removes_files_or_metadata(saved, monkeypatch):
    service, owner, inv, artifact, _, _ = saved
    from sqlalchemy.orm import Session

    original = Session.execute

    def reject_delete(session, statement, *args, **kwargs):
        if statement.is_delete:
            raise RuntimeError("Simulate transaction failure")
        return original(session, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", reject_delete)
    with pytest.raises(RuntimeError):
        DeletionService(service).remove(owner, inv.id, inv.name)
    assert service.get(owner, inv.id).name == inv.name
    assert service.storage.exists(artifact.storage_key)
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(StorageDeletion)) == 0
        assert session.scalar(select(func.count()).select_from(ReviewAudit)) == 1


def test_concurrent_erasure_and_storage_lock_retry_are_safe(saved):
    service, owner, inv, artifact, _, _ = saved

    def remove(_):
        try:
            return DeletionService(service).remove(owner, inv.id, inv.name)
        except ProductError as failure:
            return failure.code

    with FileLock(service.settings.storage_root / ".write.lock"):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(remove, range(2)))
        assert sum(isinstance(result, dict) for result in outcomes) == 1
        assert "NOT_FOUND" in outcomes
        assert (
            next(result for result in outcomes if isinstance(result, dict))["storage_cleanup"]
            == "pending"
        )
        assert service.storage.exists(artifact.storage_key)
    assert DeletionService(service).cleanup()["pending"] == 0


def test_review_activity_refreshes_retention_age(saved):
    service, owner, inv, _, run_id, _ = saved
    ReviewService(service).save(
        owner,
        run_id,
        "candidate",
        ReviewDisposition.DISMISSED,
        "Close this review for the retention fixture.",
        1,
        "close-review",
    )
    with service.database.session.begin() as session:
        session.execute(
            update(Investigation)
            .where(Investigation.id == inv.id)
            .values(updated_at=datetime.now(UTC) - timedelta(days=120))
        )
    assert inv.id in retention_report(service.settings)["eligible_investigation_ids"]
    ReviewService(service).save(
        owner,
        run_id,
        "candidate",
        ReviewDisposition.DISMISSED,
        "Review complete; shared devices explained.",
        2,
        "second-review",
    )
    assert inv.id not in retention_report(service.settings)["eligible_investigation_ids"]


def test_new_review_invalidates_a_stale_deletion_confirmation(saved):
    service, owner, inv, artifact, run_id, _ = saved
    old = service.get(owner, inv.id).updated_at.replace(tzinfo=UTC)
    ReviewService(service).save(
        owner,
        run_id,
        "candidate",
        ReviewDisposition.ESCALATED,
        "New evidence requires assessment.",
        1,
        "new-review",
    )
    with pytest.raises(ProductError) as failure:
        DeletionService(service).remove(owner, inv.id, inv.name, old)
    assert failure.value.code == "CONFLICT"
    assert service.storage.exists(artifact.storage_key)
    assert len(ReviewService(service).get(owner, run_id, "candidate")["history"]) == 2


def test_review_write_cannot_revive_a_case_deleted_after_evidence_read(saved, monkeypatch):
    service, owner, inv, _, run_id, _ = saved
    reviews = ReviewService(service)
    read = reviews._candidate

    def deleted_after_read(*args):
        read(*args)
        DeletionService(service).remove(owner, inv.id, inv.name)

    monkeypatch.setattr(reviews, "_candidate", deleted_after_read)
    with pytest.raises(ProductError) as failure:
        reviews.save(
            owner,
            run_id,
            "candidate",
            ReviewDisposition.DISMISSED,
            "Stale tab cannot recreate notes.",
            1,
            "stale-tab",
        )
    assert failure.value.code == "NOT_FOUND"


def test_retention_requires_explicit_application_and_preserves_open_reviews(saved):
    service, owner, inv, _, _, _ = saved
    expired = service.create(owner, "Expired empty case")
    with service.database.session.begin() as session:
        session.execute(
            update(Investigation)
            .where(Investigation.id.in_([inv.id, expired.id]))
            .values(updated_at=datetime.now(UTC) - timedelta(days=120))
        )
    report = retention_report(service.settings)
    assert report["eligible_investigation_ids"] == [expired.id]
    assert report["automatic_deletion"] is False
    with pytest.raises(ValueError, match="confirmation"):
        apply_retention(service.settings)
    assert service.get(owner, expired.id).name == expired.name
    result = apply_retention(service.settings, confirmed=True, limit=1)
    assert result["deleted"] == 1 and result["pending_storage_objects"] == 0
    assert service.get(owner, inv.id).name == inv.name
    assert apply_retention(service.settings, confirmed=True)["deleted"] == 0


def test_failing_cleanup_does_not_starve_unattempted_objects(saved, monkeypatch):
    service, *_ = saved
    failing = "a" * 32 + ".json"
    waiting = "b" * 32 + ".json"
    now = datetime.now(UTC)
    with service.database.session.begin() as session:
        session.add_all(
            [
                StorageDeletion(key=failing, created_at=now - timedelta(minutes=1)),
                StorageDeletion(key=waiting, created_at=now),
            ]
        )
    original = service.storage.delete

    def transient_failure(key):
        if key == failing:
            raise OSError("Storage unavailable")
        original(key)

    monkeypatch.setattr(service.storage, "delete", transient_failure)
    cleanup = DeletionService(service)
    assert cleanup.cleanup(limit=1) == {"removed": 0, "pending": 2}
    assert cleanup.cleanup(limit=1) == {"removed": 1, "pending": 1}
    with service.database.session() as session:
        assert session.get(StorageDeletion, waiting) is None
        assert session.get(StorageDeletion, failing).attempts == 1
