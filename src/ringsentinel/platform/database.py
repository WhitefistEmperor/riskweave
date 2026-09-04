"""Explicit migration entrypoint and short-lived transaction factory."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from ringsentinel.platform.settings import Settings


def make_engine(url: str):
    connect_args = {}
    if url.startswith("postgresql"):
        connect_args = {
            "connect_timeout": 5,
            "options": "-c statement_timeout=5000 -c lock_timeout=5000",
        }
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def sqlite_constraints(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return engine


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")


def main() -> None:
    settings = Settings()
    # The documented default database parent is work/; no runtime schema creation.
    Path("work").mkdir(exist_ok=True)
    database = Database(settings.database_url.get_secret_value())
    database.migrate()
    database.engine.dispose()


if __name__ == "__main__":
    main()
