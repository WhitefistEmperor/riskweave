"""Ownership, audit persistence, concurrency and safe retry of analyst decisions."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.platform.backup import create_snapshot, restore_snapshot
from ringsentinel.platform.database import Database
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import ReviewDisposition
from ringsentinel.platform.reviews import ReviewService
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


@pytest.fixture
def saved(tmp_path):
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'reviews.db'}",
        storage_root=tmp_path / "objects",
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    service = InvestigationService(db, LocalStorageBackend(settings.storage_root), settings)
    owner = Principal("review-owner")
    inv = service.create(owner, "Review lifecycle")
    payload = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100)).generate().model_dump_json()
    )
    artifact = service.attach(owner, inv.id, payload.encode(), "input.json", "application/json")
    run = service.start(owner, inv.id, artifact.id, "first")
    service.claim()
    # A persisted transport fixture exercises review lifecycle without training a model.
    service.finish(run.id, {"rings": [{"candidate": {"candidate_id": "review-candidate"}}]})
    yield service, owner, run.id
    db.engine.dispose()


def test_http_review_history_safe_retry_and_owner_isolation(saved):
    service, owner, run_id = saved
    path = f"/api/v1/runs/{run_id}/rings/review-candidate/review"
    with TestClient(create_app(settings=service.settings)) as client:
        client.headers["X-Development-User"] = owner.user_id
        initial = client.get(path).json()
        assert initial["version"] == 0 and initial["history"] == []
        assert initial["disposition"] == "unreviewed"
        body = {
            "disposition": "investigating",
            "note": "Review shared devices.",
            "expected_version": 0,
        }
        headers = {"Idempotency-Key": "review-first"}
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 200, response.text
        review = response.json()
        assert review["version"] == 1
        assert review["history"][0]["actor_id"] == owner.user_id
        assert review["history"][0]["created_at"].endswith("Z")
        assert review["updated_at"].endswith("Z")
        assert "idempotency_key" not in review["history"][0]
        assert client.post(path, json=body, headers=headers).json() == review
        assert (
            client.post(path, json={**body, "note": "Different"}, headers=headers).status_code
            == 409
        )
        assert client.post(path, json=body, headers={"Idempotency-Key": "stale"}).status_code == 409
        second = client.post(
            path,
            json={
                "disposition": "dismissed",
                "note": "Sharing explained by a family account.",
                "expected_version": 1,
            },
            headers={"Idempotency-Key": "second"},
        ).json()
        assert len(second["history"]) == 2
        assert second["history"][0] == review["history"][0]
        assert second["history"][1]["previous_disposition"] == "investigating"
        # Revisiting preserves history; changing an analyst decision doesn't edit model evidence.
        assert client.get(path).json() == second
        assert service.result(owner, run_id) == {
            "rings": [{"candidate": {"candidate_id": "review-candidate"}}]
        }
        client.headers["X-Development-User"] = "another-owner"
        assert client.get(path).status_code == 404
        assert client.post(path, json=body, headers=headers).status_code == 404
        client.headers["X-Development-User"] = owner.user_id
        assert client.get(path.replace("review-candidate", "missing")).status_code == 404
        for invalid in [" ", "\u0000", "n" * 2001]:
            assert (
                client.post(path, json={**body, "note": invalid}, headers=headers).status_code
                == 422
            )
        assert (
            client.post(path, json={**body, "expected_version": True}, headers=headers).status_code
            == 422
        )


def test_concurrent_reviews_do_not_overwrite_and_quota_keeps_retries_safe(saved):
    service, owner, run_id = saved
    reviews = ReviewService(service)
    service.settings.max_review_events_per_candidate = 1

    def save(key):
        try:
            return reviews.save(
                owner,
                run_id,
                "review-candidate",
                ReviewDisposition.INVESTIGATING,
                "Reviewing connections",
                0,
                key,
            )["version"]
        except ProductError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(save, ["one", "two"]))
    assert sorted(map(str, outcomes)) == ["1", "CONFLICT"]
    winner = "one" if outcomes[0] == 1 else "two"
    assert save(winner) == 1
    with pytest.raises(ProductError) as failure:
        reviews.save(
            owner,
            run_id,
            "review-candidate",
            ReviewDisposition.ESCALATED,
            "New finding",
            1,
            "third",
        )
    assert failure.value.code == "QUOTA_EXCEEDED"
    assert len(reviews.get(owner, run_id, "review-candidate")["history"]) == 1


def test_backup_restore_keeps_review_history_and_scope(saved, tmp_path):
    service, owner, run_id = saved
    original = ReviewService(service).save(
        owner,
        run_id,
        "review-candidate",
        ReviewDisposition.ESCALATED,
        "Manual escalation",
        0,
        "saved",
    )
    snapshot = tmp_path / "snapshot"
    create_snapshot(service.settings, snapshot, writers_stopped=True)
    restored = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'restored.db'}",
        storage_root=tmp_path / "restored",
    )
    restore_snapshot(restored, snapshot, writers_stopped=True)
    db = Database(restored.database_url.get_secret_value())
    reopened = ReviewService(
        InvestigationService(db, LocalStorageBackend(restored.storage_root), restored)
    )
    result = reopened.get(owner, run_id, "review-candidate")
    assert result["version"] == original["version"]
    assert result["history"][0].note == "Manual escalation"
    with pytest.raises(ProductError):
        reopened.get(Principal("other"), run_id, "review-candidate")
    db.engine.dispose()


def test_same_candidate_id_in_a_new_run_starts_with_independent_review(saved):
    service, owner, run_id = saved
    reviews = ReviewService(service)
    reviews.save(
        owner,
        run_id,
        "review-candidate",
        ReviewDisposition.DISMISSED,
        "Explained sharing",
        0,
        "first-review",
    )
    original = service.run(owner, run_id)
    next_run = service.start(owner, original.investigation_id, original.artifact_id, "next-run")
    service.claim()
    service.finish(next_run.id, {"rings": [{"candidate": {"candidate_id": "review-candidate"}}]})
    assert reviews.get(owner, next_run.id, "review-candidate")["version"] == 0
    assert reviews.get(owner, run_id, "review-candidate")["disposition"] == "dismissed"


def test_upgrade_preserves_existing_investigation_and_requires_new_tables(tmp_path):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from ringsentinel.api.platform_api import dependencies_ready
    from ringsentinel.platform.models import Investigation, Status, User

    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'old.db'}",
        storage_root=tmp_path / "old-objects",
    )
    db = Database(settings.database_url.get_secret_value())
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "src/ringsentinel/platform/migrations")
    )
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    with db.session.begin() as session:
        session.add(User(id="existing-owner"))
        session.flush()
        inv = Investigation(
            owner_id="existing-owner",
            name="Existing case",
            status=Status.CREATED,
            source_metadata={},
            analysis_metadata={},
        )
        session.add(inv)
    service = InvestigationService(db, LocalStorageBackend(settings.storage_root), settings)
    assert not dependencies_ready(service)
    db.migrate()
    assert dependencies_ready(service)
    assert service.get(Principal("existing-owner"), inv.id).name == "Existing case"
    db.engine.dispose()
