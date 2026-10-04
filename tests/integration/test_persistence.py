import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from ringsentinel.platform.database import Database
from ringsentinel.platform.models import Investigation, Status, User


def test_migration_persistence_and_foreign_keys(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    first = Database(url)
    first.migrate()
    first.migrate()  # Idempotent migration application, not create_all.
    assert set(inspect(first.engine).get_table_names()) == {
        "alembic_version",
        "users",
        "investigations",
        "artifacts",
        "analysis_runs",
        "result_fragments",
        "candidate_reviews",
        "review_audit",
        "storage_deletions",
        "stored_objects",
        "upload_sessions",
        "upload_parts",
        "analysis_dispatches",
        "dispatch_budgets",
        "dispatch_schedules",
    }
    with first.session.begin() as session:
        session.add(User(id="alice"))
        session.flush()
        investigation = Investigation(owner_id="alice", name="Case", status=Status.CREATED)
        session.add(investigation)
    first.engine.dispose()
    second = Database(url)
    with second.session() as session:
        persisted = session.scalar(select(Investigation))
        assert persisted.id == investigation.id
        assert persisted.status == Status.CREATED
        assert persisted.created_at is not None
    with pytest.raises(IntegrityError), second.session.begin() as session:
        session.add(Investigation(owner_id="missing", name="Bad", status=Status.CREATED))
    second.engine.dispose()


def test_production_rejects_development_identity():
    from ringsentinel.platform.settings import Settings

    with pytest.raises(ValueError):
        Settings(environment="production")


def test_upgrade_preserves_existing_review_history_and_foreign_keys(tmp_path):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    import ringsentinel.platform.database as database_module

    database = Database(f"sqlite:///{tmp_path / 'previous-release.db'}")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0003")
        timestamp = "2026-01-01 00:00:00"
        rows = [
            ("users", {"id": "owner", "created_at": timestamp, "updated_at": timestamp}),
            (
                "investigations",
                {
                    "id": "case",
                    "owner_id": "owner",
                    "name": "Existing",
                    "status": "completed",
                    "source_metadata": "{}",
                    "analysis_metadata": "{}",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            ),
            (
                "artifacts",
                {
                    "id": "input",
                    "investigation_id": "case",
                    "original_name": "input.json",
                    "storage_key": "a" * 32 + ".json",
                    "content_type": "application/json",
                    "size_bytes": 2,
                    "checksum": "a" * 64,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            ),
            (
                "analysis_runs",
                {
                    "id": "run",
                    "investigation_id": "case",
                    "artifact_id": "input",
                    "status": "completed",
                    "idempotency_key": "analysis",
                    "version_metadata": "{}",
                    "configuration_snapshot": "{}",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            ),
            (
                "candidate_reviews",
                {
                    "run_id": "run",
                    "candidate_id": "candidate",
                    "disposition": "investigating",
                    "version": 1,
                    "updated_at": timestamp,
                },
            ),
            (
                "review_audit",
                {
                    "id": "audit",
                    "run_id": "run",
                    "candidate_id": "candidate",
                    "actor_id": "owner",
                    "previous_disposition": "unreviewed",
                    "disposition": "investigating",
                    "version": 1,
                    "note": "Keep this history",
                    "idempotency_key": "review",
                    "created_at": timestamp,
                },
            ),
        ]
        for table, row in rows:
            columns = ", ".join(row)
            bindings = ", ".join(f":{key}" for key in row)
            connection.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({bindings})"), row)
    database.migrate()
    database.migrate()
    with database.session() as session:
        assert (
            session.scalar(text("SELECT note FROM review_audit WHERE id='audit'"))
            == "Keep this history"
        )
        assert session.scalar(text("SELECT version FROM candidate_reviews WHERE run_id='run'")) == 1
        assert (
            session.scalar(text("SELECT status FROM analysis_runs WHERE id='run'")) == "completed"
        )
    with pytest.raises(IntegrityError), database.session.begin() as session:
        session.execute(
            text(
                "INSERT INTO candidate_reviews "
                "(run_id,candidate_id,disposition,version,updated_at) "
                "VALUES ('missing','bad','investigating',1,'2026-01-01 00:00:00')"
            )
        )
    database.engine.dispose()
