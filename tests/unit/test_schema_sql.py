"""The committed paste-in schema stays identical to the migrations."""

from pathlib import Path

from ringsentinel.platform.database import Database, migration_sql

SCRIPT = Path(__file__).parents[2] / "deploy" / "supabase" / "riskweave_schema.sql"


def test_committed_schema_matches_migrations():
    committed = SCRIPT.read_text(encoding="utf-8").replace("\r\n", "\n")
    header, _, body = committed.partition("\n\n")
    assert f"migration {Database.revision}" in header, "Regenerate riskweave_schema.sql"
    assert body == migration_sql().replace("\r\n", "\n"), (
        "Regenerate with: uv run --locked ringsentinel-migrate --sql"
    )


def test_schema_is_one_transaction_ending_at_current_revision():
    sql = migration_sql()
    assert sql.lstrip().startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    assert f"SET version_num='{Database.revision}'" in sql
