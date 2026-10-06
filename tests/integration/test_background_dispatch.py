"""Delivery interruption and real SDK inference, without cloud credentials or user data."""

import asyncio
import importlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import numpy as np
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.api.app import create_app
from ringsentinel.api.platform_api import dependencies_ready
from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    EventFeatureRow,
    FeatureTable,
)
from ringsentinel.models.artifact import write_artifact
from ringsentinel.models.tabular import BoostedTreeDetector
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.dispatch import DeliveryCoordinator, execute_dispatch, exhaust_dispatch
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import (
    AnalysisDispatch,
    AnalysisRun,
    DispatchBudget,
    DispatchSchedule,
    Status,
    StoredBlob,
    utcnow,
)
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings


class Delivery:
    """Transport failures only; this adapter never supplies inference results."""

    def __init__(self):
        self.calls = []
        self.controllers = 0
        self.fail = False
        self.state = "running"

    async def analysis(self, run_id, ticket):
        self.calls.append((run_id, ticket))
        if self.fail:
            raise RuntimeError("provider URL and secret must not be retained")
        return "wrun_" + str(len(self.calls)).zfill(26)

    async def reconcile(self):
        self.controllers += 1
        return "wrun_" + str(1000 + self.controllers).zfill(26)

    async def status(self, workflow_id):
        return self.state


@pytest.fixture
def service(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'db'}",
        storage_root=tmp_path / "scratch",
        storage_backend="database",
        execution_mode="request",
        background_dispatch="vercel_workflow",
        dispatch_cron_secret="test-only-cron-secret",
        analysis_timeout_seconds=60,
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    yield InvestigationService(db, storage_for(db, settings), settings)
    db.engine.dispose()


def saved(service, owner="alice", key="first"):
    principal = Principal(owner)
    case = service.create(principal, "Background test case")
    data = SyntheticPaymentGenerator(GenerationConfig(transactions=100)).generate()
    artifact = service.attach(
        principal, case.id, data.model_dump_json().encode(), "input.json", "application/json"
    )
    return principal, case, artifact, service.start(principal, case.id, artifact.id, key)


def due(service, run_id):
    with service.database.write() as session:
        session.get(AnalysisDispatch, run_id).next_attempt_at = utcnow() - timedelta(seconds=1)


def test_intent_and_quota_are_atomic_and_idempotent(service):
    service.settings.dispatch_starts_per_month = 1
    owner, case, artifact, run = saved(service)
    same = service.start(owner, case.id, artifact.id, "first")
    assert same.id == run.id and same.dispatch_state == "pending"
    with pytest.raises(ProductError) as denied:
        saved(service, "bob")
    assert denied.value.code == "QUOTA_EXCEEDED"
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 1
        assert session.scalar(select(func.count()).select_from(AnalysisDispatch)) == 1
        assert session.scalar(select(DispatchBudget.starts)) == 1


def test_api_ack_owner_scoping_legacy_client_and_cron_authorization(service):
    delivery = Delivery()
    owner, case, artifact, run = saved(service)
    with TestClient(create_app(settings=service.settings, workflow_delivery=delivery)) as client:
        headers = {"X-Development-User": owner.user_id, "Idempotency-Key": "first"}
        path = f"/api/v1/investigations/{case.id}/runs"
        ack = client.post(path, headers=headers, json={"artifact_id": artifact.id})
        assert ack.status_code == 202, ack.text
        assert ack.json()["id"] == run.id and ack.json()["dispatch_state"] == "accepted"
        assert ack.json()["status"] == "queued"  # Delivery is separate from execution.
        for _ in range(2):
            assert (
                client.post(path, headers=headers, json={"artifact_id": artifact.id}).status_code
                == 202
            )
        assert len(delivery.calls) == 1 and delivery.controllers == 1
        assert (
            client.post(f"/api/v1/runs/{run.id}/execute", headers=headers).json()["status"]
            == "queued"
        )
        denied = client.post(
            f"/api/v1/runs/{run.id}/execute", headers={"X-Development-User": "bob"}
        )
        assert denied.status_code == 404 and len(delivery.calls) == 1
        cron = "/api/v1/operations/reconcile-delivery"
        assert client.get(cron, headers=headers).status_code == 401
        assert client.get(cron, headers={"Authorization": "Bearer wrong"}).status_code == 401
        checked = client.get(cron, headers={"Authorization": "Bearer test-only-cron-secret"})
        assert checked.status_code == 200 and checked.json()["status"] == "checked"
        assert delivery.controllers == 1
        assert client.get("/api/v1/ready").status_code == 200


def test_transient_and_exhausted_delivery_failures_are_bounded_and_safe(service):
    owner, case, _, run = saved(service)
    delivery = Delivery()
    delivery.fail = True
    coordinator = DeliveryCoordinator(service, delivery)
    asyncio.run(coordinator.publish(run.id))
    assert service.run(owner, run.id).dispatch_state == "pending"
    asyncio.run(coordinator.publish(run.id))  # Backoff prevents an immediate retry.
    assert len(delivery.calls) == 1
    for _ in range(2):
        due(service, run.id)
        asyncio.run(coordinator.reconcile())
    failed = service.run(owner, run.id)
    assert failed.status == Status.FAILED and failed.error_code == "DISPATCH_FAILED"
    assert failed.active_slot is None and failed.executor_slot is None
    assert "provider" not in failed.error_message_safe
    assert service.get(owner, case.id).status == Status.FAILED
    with service.database.session() as session:
        item = session.get(AnalysisDispatch, run.id)
        assert item.attempts == 3 and item.last_error_code == "DISPATCH_FAILED"
        assert session.scalar(select(DispatchBudget.starts)) == 3
    asyncio.run(coordinator.reconcile())
    assert len(delivery.calls) == 3


def test_concurrent_instances_crash_lease_and_late_ack_are_fenced(service):
    _, _, _, run = saved(service)
    db = Database(service.settings.database_url.get_secret_value())
    other = InvestigationService(db, storage_for(db, service.settings), service.settings)
    first = DeliveryCoordinator(service, Delivery())
    second = DeliveryCoordinator(other, Delivery())
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(item._claim, run.id) for item in [first, second]]
            claims = [future.result() for future in futures]
        assert sum(claim is not None for claim in claims) == 1
        old_ticket, old_lease = next(claim for claim in claims if claim)
        assert second._claim(run.id) is None
        # A process died after queue submission but before acknowledging its lease.
        with service.database.write() as session:
            session.get(AnalysisDispatch, run.id).lease_until = utcnow() - timedelta(seconds=1)
        new_ticket, new_lease = second._claim(run.id)
        assert new_ticket == old_ticket and new_lease != old_lease
        first._settle(run.id, old_lease, "wrun_" + "1" * 26)
        with db.session() as session:
            assert session.get(AnalysisDispatch, run.id).workflow_id is None
        second._settle(run.id, new_lease, "wrun_" + "2" * 26)
        with db.session() as session:
            assert session.get(AnalysisDispatch, run.id).workflow_id == "wrun_" + "2" * 26
    finally:
        db.engine.dispose()


def test_cancelled_publication_retains_retry_and_original_run(service):
    owner, _, _, run = saved(service)

    class Interrupted(Delivery):
        async def analysis(self, run_id, ticket):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(DeliveryCoordinator(service, Interrupted()).publish(run.id))
    with service.database.session() as session:
        item = session.get(AnalysisDispatch, run.id)
        assert item.attempts == 1 and item.lease_token is None and item.workflow_id is None
    assert service.run(owner, run.id).status == Status.QUEUED
    due(service, run.id)
    delivery = Delivery()
    asyncio.run(DeliveryCoordinator(service, delivery).reconcile())
    assert service.run(owner, run.id).dispatch_state == "accepted"
    assert delivery.calls[0][0] == run.id


def test_provider_terminal_failure_repairs_delivery_without_new_analysis(service):
    owner, _, _, run = saved(service)
    delivery = Delivery()
    coordinator = DeliveryCoordinator(service, delivery)
    asyncio.run(coordinator.publish(run.id))
    delivery.state = "failed"
    due(service, run.id)
    asyncio.run(coordinator.reconcile())
    assert len(delivery.calls) == 2 and delivery.calls[0] == delivery.calls[1]
    assert service.run(owner, run.id).status == Status.QUEUED
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 1


def test_accepted_status_checks_do_not_starve_unpublished_work(service):
    delivery = Delivery()
    coordinator = DeliveryCoordinator(service, delivery)
    _, _, _, older = saved(service)
    asyncio.run(coordinator.publish(older.id))
    _, _, _, newer = saved(service, "bob")
    with service.database.write() as session:
        session.get(AnalysisDispatch, older.id).next_attempt_at = utcnow() - timedelta(days=1)
    asyncio.run(coordinator.reconcile(limit=1))
    assert len(delivery.calls) == 1
    asyncio.run(coordinator.reconcile(limit=1))
    assert delivery.calls[-1][0] == newer.id


def test_budget_exhaustion_in_recovery_and_capacity_failure_preserve_running_work(service):
    service.settings.dispatch_starts_per_month = 1
    owner, _, _, run = saved(service)
    coordinator = DeliveryCoordinator(service, Delivery())
    coordinator._claim(run.id)
    with service.database.write() as session:
        item = session.get(AnalysisDispatch, run.id)
        item.lease_until = utcnow() - timedelta(seconds=1)
    assert coordinator._claim(run.id) is None
    assert service.run(owner, run.id).error_code == "QUOTA_EXCEEDED"
    service.settings.dispatch_starts_per_month = 10
    owner, _, _, running = saved(service, key="healthy")
    with service.database.session() as session:
        ticket = session.get(AnalysisDispatch, running.id).ticket
    assert exhaust_dispatch(service, running.id, "incorrect-ticket") == "deleted"
    assert service.claim(running.id, owner) == running.id
    assert exhaust_dispatch(service, running.id, ticket) == "running"
    assert service.run(owner, running.id).error_code is None
    owner, _, _, queued = saved(service, key="capacity")
    with service.database.session() as session:
        ticket = session.get(AnalysisDispatch, queued.id).ticket
    assert exhaust_dispatch(service, queued.id, ticket) == "failed"
    assert service.run(owner, queued.id).error_code == "CAPACITY_TIMEOUT"


def test_erasure_removes_intent_and_stale_workflow_cannot_recreate_case(service):
    owner, case, _, run = saved(service)
    with service.database.session() as session:
        ticket = session.get(AnalysisDispatch, run.id).ticket
    exhaust_dispatch(service, run.id, ticket)
    assert (
        DeletionService(service).remove(owner, case.id, case.name)["storage_cleanup"] == "complete"
    )
    assert execute_dispatch(service, run.id, ticket) == "deleted"
    assert exhaust_dispatch(service, run.id, ticket) == "deleted"
    with service.database.session() as session:
        assert session.get(AnalysisDispatch, run.id) is None
        assert session.scalar(select(func.count()).select_from(StoredBlob)) == 0
        assert session.scalar(select(DispatchBudget.starts)) == 1  # Anonymous operational total.


def test_deployment_model_change_cannot_silently_change_saved_run_provenance(service):
    owner, _, _, run = saved(service)
    with service.database.session() as session:
        ticket = session.get(AnalysisDispatch, run.id).ticket
    service.settings.model_artifact_sha256 = "a" * 64
    assert execute_dispatch(service, run.id, ticket) == "failed"
    failed = service.run(owner, run.id)
    assert failed.error_code == "MODEL_VERSION_UNAVAILABLE"
    assert failed.version_metadata["model_artifact_sha256"] == "runtime-trained"
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(StoredBlob)) == 1


def test_readiness_checks_outbox_and_production_rejects_embedded_engine(service, monkeypatch):
    with service.database.write() as session:
        session.execute(text("DROP TABLE analysis_dispatches"))
    assert not dependencies_ready(service)
    with pytest.raises(ValueError, match="enabled request"):
        Settings(background_dispatch="vercel_workflow")
    production = service.settings.model_copy(update={"environment": "production"})
    monkeypatch.delenv("VERCEL_DEPLOYMENT_ID", raising=False)
    with pytest.raises(ValueError, match="managed runtime"):
        create_app(settings=production, workflow_delivery=Delivery())


def test_populated_previous_migration_preserves_case_and_legacy_execution(service):
    service.settings.background_dispatch = "none"
    owner, case, artifact, run = saved(service)
    config = Config()
    module = importlib.import_module("ringsentinel.platform.migrations")
    config.set_main_option("script_location", str(next(iter(module.__path__))))
    with service.database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0005")
    service.database.migrate()
    service.database.migrate()
    assert service.get(owner, case.id).name == case.name
    assert service.artifacts(owner, case.id)[0].checksum == artifact.checksum
    restored = service.run(owner, run.id)
    assert restored.status == Status.QUEUED and restored.dispatch_state is None
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisDispatch)) == 0


def test_real_sdk_finishes_saved_analysis_without_browser_execution(service, monkeypatch, tmp_path):
    features = TRANSACTION_FEATURES + NETWORK_FEATURES
    table = FeatureTable(
        tuple(
            EventFeatureRow(str(i), datetime.now(UTC), {name: float(i % 7) for name in features})
            for i in range(60)
        )
    )
    detector = BoostedTreeDetector(features, random_state=105)
    detector.fit((table,), (np.array([i % 2 for i in range(60)]),))
    model = tmp_path / "test-only-trusted-model.joblib"
    metadata = write_artifact(detector, 0.5, model)
    service.settings.model_artifact_path = model
    service.settings.model_artifact_sha256 = metadata["sha256"]
    for name, value in {
        "RINGSENTINEL_ENVIRONMENT": "test",
        "RINGSENTINEL_DATABASE_URL": service.settings.database_url.get_secret_value(),
        "RINGSENTINEL_STORAGE_ROOT": str(service.settings.storage_root),
        "RINGSENTINEL_STORAGE_BACKEND": "database",
        "RINGSENTINEL_EXECUTION_MODE": "request",
        "RINGSENTINEL_BACKGROUND_DISPATCH": "vercel_workflow",
        "RINGSENTINEL_ANALYSIS_TIMEOUT_SECONDS": "60",
        "RINGSENTINEL_MODEL_ARTIFACT_PATH": str(model),
        "RINGSENTINEL_MODEL_ARTIFACT_SHA256": metadata["sha256"],
        "WORKFLOW_TARGET_WORLD": "local",
        "WORKFLOW_LOCAL_DATA_DIR": str(tmp_path / "sdk-events"),
    }.items():
        monkeypatch.setenv(name, value)
    # Private reset/cleanup is test isolation only; application code uses public SDK APIs.
    from vercel import workflow
    from vercel.workflow._internal import world

    world.set_world(None)
    from ringsentinel.platform.workflows import analyze_saved_run

    async def exercise():
        controller = None
        try:
            # Initialize embedded queue in this task so shutdown owns its AnyIO scope.
            stale = await workflow.start(
                analyze_saved_run, run_id=str(uuid4()), ticket=str(uuid4())
            )
            async with asyncio.timeout(30):
                assert await stale.return_value() == "deleted"
            app = create_app(settings=service.settings)
            owner = Principal("alice")
            case = service.create(owner, "Real SDK saved analysis")
            content = SyntheticPaymentGenerator(GenerationConfig(transactions=100)).generate()
            artifact = service.attach(
                owner, case.id, content.model_dump_json().encode(), "x", "application/json"
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                reply = await client.post(
                    f"/api/v1/investigations/{case.id}/runs",
                    headers={"X-Development-User": "alice", "Idempotency-Key": "sdk-real"},
                    json={"artifact_id": artifact.id},
                )
                assert reply.status_code == 202, reply.text
                run_id = reply.json()["id"]
                with service.database.session() as session:
                    intent = session.get(AnalysisDispatch, run_id)
                    provider_id, ticket = intent.workflow_id, intent.ticket
                    controller = session.scalar(select(DispatchSchedule.workflow_id))
                async with asyncio.timeout(60):
                    assert await workflow.Run(provider_id).return_value() == "completed"
                # No /execute call or status polling drove inference.
                completed = service.run(owner, run_id)
                result = service.result(owner, run_id)
                assert completed.status == Status.COMPLETED and result["event_count"] == len(
                    content.events
                )
                assert completed.version_metadata["model_artifact_sha256"] == metadata["sha256"]
                checksum = completed.result_checksum
                duplicate = await workflow.start(analyze_saved_run, run_id=run_id, ticket=ticket)
                async with asyncio.timeout(30):
                    assert await duplicate.return_value() == "completed"
                assert service.run(owner, run_id).result_checksum == checksum
                with service.database.session() as session:
                    assert session.scalar(select(func.count()).select_from(StoredBlob)) == 2
                denied = await client.get(
                    f"/api/v1/runs/{run_id}/results", headers={"X-Development-User": "bob"}
                )
                assert denied.status_code == 404
                DeletionService(service).remove(owner, case.id, case.name)
                deleted = await workflow.start(analyze_saved_run, run_id=run_id, ticket=ticket)
                async with asyncio.timeout(30):
                    assert await deleted.return_value() == "deleted"
            app.state.platform.database.engine.dispose()
        finally:
            if controller:
                await workflow.Run(controller).terminate()
            await world.get_world().aclose()
            world.set_world(None)

    asyncio.run(exercise())
