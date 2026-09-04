"""Offline compilation is not a claim of live PostgreSQL verification."""

import importlib
import io

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_mock_engine

from ringsentinel.platform.backup import pg_command
from ringsentinel.platform.database import Database
from ringsentinel.platform.models import Base


def test_actual_migration_and_metadata_compile_for_postgresql():
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    revision = importlib.import_module("ringsentinel.platform.migrations.versions.0001_foundation")
    with Operations.context(context):
        revision.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE analysis_runs" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "UNIQUE (active_slot)" in sql
    assert "FOREIGN KEY(owner_id) REFERENCES users" in sql
    statements = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda stmt, *a, **k: statements.append(str(stmt.compile(dialect=engine.dialect))),
    )
    Base.metadata.create_all(engine)
    assert any("CREATE TABLE artifacts" in stmt for stmt in statements)


def test_postgres_backup_commands_keep_password_out_of_arguments(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "ringsentinel.platform.backup.subprocess.run",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )
    db = Database("postgresql+psycopg://user:unit-only-password@database/test?sslmode=require")
    try:
        pg_command(db, "backup", tmp_path / "database.dump")
        pg_command(db, "restore", tmp_path / "database.dump")
    finally:
        db.engine.dispose()
    for args, kwargs in calls:
        assert "unit-only-password" not in str(args)
        assert kwargs["env"]["PGPASSWORD"] == "unit-only-password"
        assert kwargs["env"]["PGSSLMODE"] == "require"
        assert kwargs["timeout"] == 300
        assert kwargs.get("shell", False) is False
    assert "--single-transaction" in calls[1][0]
