"""Immutable fragment digests without duplicating result payload bytes."""

import hashlib
import re

from sqlalchemy import func, select, text

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import AnalysisRun, ResultFragment, Status

CHUNK_BYTES = 2_000_000


def index_in(session, run, content):
    run.result_size_bytes = len(content)
    for index, offset in enumerate(range(0, len(content), CHUNK_BYTES)):
        part = memoryview(content)[offset : offset + CHUNK_BYTES]
        session.add(
            ResultFragment(
                run_id=run.id,
                part_index=index,
                size_bytes=len(part),
                checksum=hashlib.sha256(part).hexdigest(),
            )
        )


def metadata(service, run):
    size = run.result_size_bytes
    if type(size) is not int or not 0 < size <= 500_000_000:
        raise ProductError("INTERNAL_ERROR")
    with service.database.session() as session:
        rows = list(
            session.scalars(
                select(ResultFragment)
                .where(ResultFragment.run_id == run.id)
                .order_by(ResultFragment.part_index)
            )
        )
    count = (size + CHUNK_BYTES - 1) // CHUNK_BYTES
    if len(rows) != count or not re.fullmatch(r"[a-f0-9]{64}", run.result_checksum or ""):
        raise ProductError("INTERNAL_ERROR")
    for index, row in enumerate(rows):
        expected = min(CHUNK_BYTES, size - index * CHUNK_BYTES)
        if (
            row.part_index != index
            or row.size_bytes != expected
            or not re.fullmatch(r"[a-f0-9]{64}", row.checksum)
        ):
            raise ProductError("INTERNAL_ERROR")
    if count == 1 and rows[0].checksum != run.result_checksum:
        raise ProductError("INTERNAL_ERROR")
    return rows


def read_part(service, run, row):
    if service.storage.size(run.result_reference) != run.result_size_bytes:
        raise ProductError("INTERNAL_ERROR")
    part = service.storage.read_range(
        run.result_reference, row.part_index * CHUNK_BYTES, row.size_bytes
    )
    if len(part) != row.size_bytes or hashlib.sha256(part).hexdigest() != row.checksum:
        raise ProductError("INTERNAL_ERROR")
    return part


def existing_database(database):
    from pathlib import Path

    path = database.engine.url.database
    if (
        database.engine.dialect.name == "sqlite"
        and path != ":memory:"
        and (not path or not Path(path).is_file())
    ):
        raise ValueError("Existing migrated database required")
    with database.session() as session:
        if session.scalar(text("SELECT version_num FROM alembic_version")) != database.revision:
            raise ValueError("Current migration required")


def index_existing(service, *, writers_stopped=False, limit=100):
    """Explicit maintenance only; preserve bytes, checksums and existing indices."""
    if not writers_stopped or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Stop writers and choose a bounded batch")
    existing_database(service.database)
    indexed = 0
    for _ in range(limit):
        with service.database.write() as session:
            if session.scalar(
                select(func.count())
                .select_from(AnalysisRun)
                .where(AnalysisRun.status.in_([Status.QUEUED, Status.RUNNING]))
            ):
                raise ValueError("Active analysis prevents result indexing")
            run = session.scalar(
                select(AnalysisRun)
                .where(
                    AnalysisRun.status == Status.COMPLETED, AnalysisRun.result_size_bytes.is_(None)
                )
                .order_by(AnalysisRun.id)
                .limit(1)
            )
            if run is None:
                break
            if (
                not run.result_reference
                or not run.result_checksum
                or session.scalar(
                    select(ResultFragment.run_id).where(ResultFragment.run_id == run.id).limit(1)
                )
            ):
                raise ProductError("INTERNAL_ERROR")
            content = service.storage.read(run.result_reference)
            if (
                not 0 < len(content) <= 500_000_000
                or hashlib.sha256(content).hexdigest() != run.result_checksum
            ):
                raise ProductError("INTERNAL_ERROR")
            index_in(session, run, content)
            del content
            indexed += 1
    return indexed


def main():
    import argparse
    import json

    from ringsentinel.platform.database import Database
    from ringsentinel.platform.database_storage import storage_for
    from ringsentinel.platform.service import InvestigationService
    from ringsentinel.platform.settings import Settings

    parser = argparse.ArgumentParser(description="Index verified legacy results during maintenance")
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    database = None
    try:
        if not args.writers_stopped:
            raise ValueError("Stop all writers first")
        settings = Settings()
        database = Database(settings.database_url.get_secret_value())
        existing_database(database)
        service = InvestigationService(database, storage_for(database, settings), settings)
        count = index_existing(service, writers_stopped=args.writers_stopped, limit=args.limit)
        print(json.dumps({"status": "indexed", "count": count}))
    except Exception:
        print(json.dumps({"status": "unavailable", "code": "RESULT_INDEX_UNAVAILABLE"}))
        raise SystemExit(2) from None
    finally:
        if database:
            database.engine.dispose()


if __name__ == "__main__":
    main()
