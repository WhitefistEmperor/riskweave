import pytest
from sqlalchemy import inspect, select
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
