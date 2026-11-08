"""Supabase pooler detection and engine configuration (no live connection)."""

import pytest
from sqlalchemy import event
from sqlalchemy.pool import NullPool

from ringsentinel.platform import database
from ringsentinel.platform.database import make_engine, pooler_mode
from ringsentinel.platform.locking import ExecutorLease

TRANSACTION = (
    "postgresql+psycopg://postgres.abcd:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
)
SESSION = TRANSACTION.replace(":6543/", ":5432/")


def test_pooler_detection():
    assert pooler_mode(TRANSACTION) == "transaction"
    assert pooler_mode(SESSION) == "session"
    assert pooler_mode("postgresql+psycopg://u:p@db.abcd.supabase.co:5432/postgres") is None
    assert pooler_mode("postgresql+psycopg://u:p@pooler.supabase.com.evil.test:6543/x") is None
    assert pooler_mode("sqlite:///./work/x.db") is None


def captured_engine(monkeypatch, url):
    calls = {}
    original = database.create_engine

    def spy(target, **kwargs):
        calls.update(kwargs)
        return original(target, **kwargs)

    monkeypatch.setattr(database, "create_engine", spy)
    return make_engine(url), calls


def test_transaction_pooler_disables_prepares_and_scopes_timeouts(monkeypatch):
    engine, calls = captured_engine(monkeypatch, TRANSACTION)
    assert calls["poolclass"] is NullPool
    assert calls["connect_args"] == {"connect_timeout": 5, "prepare_threshold": None}
    assert event.contains(engine, "begin", next(iter(engine.dispatch.begin)))


def test_session_pooler_keeps_prepares_but_scopes_timeouts(monkeypatch):
    engine, calls = captured_engine(monkeypatch, SESSION)
    assert calls["poolclass"] is NullPool
    assert calls["connect_args"] == {"connect_timeout": 5}
    assert len(engine.dispatch.begin) == 1


def test_direct_postgres_is_unchanged(monkeypatch):
    engine, calls = captured_engine(monkeypatch, "postgresql+psycopg://u:p@db.example.test/x")
    assert calls["pool_pre_ping"] is True and "poolclass" not in calls
    assert calls["connect_args"]["options"] == database.SESSION_TIMEOUTS
    assert len(engine.dispatch.begin) == 0


def test_executor_lease_refuses_transaction_pooler(tmp_path):
    class Fake:
        engine = make_engine(TRANSACTION)

    with pytest.raises(RuntimeError, match="session pooler"):
        ExecutorLease(Fake(), tmp_path).acquire()
