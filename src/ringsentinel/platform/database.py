"""Explicit migration entrypoint and short-lived transaction factory."""

from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, make_url, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from ringsentinel.platform.settings import Settings

SESSION_TIMEOUTS = "-c statement_timeout=5000 -c lock_timeout=5000"


def pooler_mode(url: str) -> str | None:
    """Detect an external Supabase (Supavisor) pooler from the connection URL.

    Supabase's direct database host is IPv6-only, so serverless hosts such as Vercel
    connect through the pooler: port 6543 is transaction mode, 5432 session mode.
    """
    if not url.startswith("postgresql"):
        return None
    parsed = make_url(url)
    if not (parsed.host or "").endswith(".pooler.supabase.com"):
        return None
    return "transaction" if parsed.port == 6543 else "session"


def make_engine(url: str):
    connect_args = {}
    options: dict = {"pool_pre_ping": True}
    mode = pooler_mode(url)
    if url.startswith("postgresql"):
        connect_args = {"connect_timeout": 5, "options": SESSION_TIMEOUTS}
    if mode is not None:
        # The external pooler owns pooling; holding idle connections per serverless
        # instance would exhaust its small client allowance.
        options = {"poolclass": NullPool}
        # Poolers may reject startup options; apply the same limits per transaction.
        connect_args = {"connect_timeout": 5}
    if mode == "transaction":
        # Transaction pooling shares server connections between clients, so
        # server-side prepared statements are unsafe.
        connect_args["prepare_threshold"] = None
    engine = create_engine(url, connect_args=connect_args, **options)
    if mode is not None:

        @event.listens_for(engine, "begin")
        def transaction_timeouts(connection):
            # Scoped to this transaction, so nothing leaks to another pooled client.
            connection.exec_driver_sql("SET LOCAL statement_timeout = 5000")
            connection.exec_driver_sql("SET LOCAL lock_timeout = 5000")

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def sqlite_constraints(connection, _):
            connection.create_function(
                "riskweave_lower",
                1,
                lambda value: value.lower() if isinstance(value, str) else value,
                deterministic=True,
            )
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return engine


class Database:
    revision = "0010"

    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    @contextmanager
    def write(self):
        """Serialize admission and mutations across processes and hosts."""
        with self.session.begin() as session:
            if self.engine.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            else:
                session.execute(text("SELECT pg_advisory_xact_lock(593002)"))
            yield session


def main() -> None:
    settings = Settings()
    # The documented default database parent is work/; no runtime schema creation.
    Path("work").mkdir(exist_ok=True)
    database = Database(settings.database_url.get_secret_value())
    database.migrate()
    database.engine.dispose()


if __name__ == "__main__":
    main()
