"""Operator counts detect stalled work without changing saved lifecycle records."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.database import Database
from ringsentinel.platform.models import AnalysisRun, Status, utcnow
from ringsentinel.platform.operations import report
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


def test_report_detects_overdue_work_and_retains_private_records(tmp_path):
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


def test_report_does_not_create_missing_sqlite_database(tmp_path):
    path = tmp_path / "not-created.db"
    database = Database(f"sqlite:///{path}")
    try:
        with pytest.raises(ValueError, match="existing migrated"):
            report(database)
        assert not path.exists()
    finally:
        database.engine.dispose()
