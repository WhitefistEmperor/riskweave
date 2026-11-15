"""Checksummed snapshots. Never overwrites a database, storage root or snapshot.

Stop every application writer before use. An explicit operator acknowledgement is required;
executor/child locks also reject an accidentally running supported executor.
Opt-in online backups require PostgreSQL with database object storage; restore is offline.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import DatabaseStorageBackend, storage_for
from ringsentinel.platform.locking import ExecutorLease, FileLock
from ringsentinel.platform.models import (
    AnalysisRun,
    Artifact,
    Investigation,
    Status,
    StorageDeletion,
)
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import StorageBackend


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pg_command(database: Database, action: str, path: Path, *, snapshot: str | None = None):
    """Use standard PostgreSQL tools, no shell and no passwords in argv or output."""
    url = database.engine.url
    if action not in {"backup", "restore"}:
        raise ValueError("Unsupported PostgreSQL operation")
    if snapshot is not None and (
        action != "backup" or not re.fullmatch(r"[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+", snapshot)
    ):
        raise ValueError("Invalid exported snapshot")
    environment = dict(os.environ)
    environment.update(
        PGHOST=url.host or "localhost",
        PGPORT=str(url.port or 5432),
        PGUSER=url.username or "",
        PGPASSWORD=url.password or "",
        PGDATABASE=url.database or "",
        PGCONNECT_TIMEOUT="5",
    )
    # Preserve explicit libpq TLS configuration from the SQLAlchemy URL.
    for key in ("sslmode", "sslrootcert", "sslcert", "sslkey"):
        if key in url.query:
            environment["PG" + key.upper()] = str(url.query[key])
    args = (
        ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(path)]
        if action == "backup"
        else [
            "pg_restore",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname",
            url.database,
            str(path),
        ]
    )
    if snapshot is not None:
        args.append("--snapshot=" + snapshot)
    try:
        subprocess.run(
            args,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(
            "PostgreSQL backup/restore command failed; inspect private operator diagnostics"
        ) from None


def verify_references_in(session, read):
    for obj in session.scalars(select(Artifact)):
        content = read(obj.storage_key)
        if len(content) != obj.size_bytes or hashlib.sha256(content).hexdigest() != obj.checksum:
            raise ValueError("Artifact integrity check failed")
    for run in session.scalars(select(AnalysisRun).where(AnalysisRun.status == Status.COMPLETED)):
        if (
            not run.result_reference
            or hashlib.sha256(read(run.result_reference)).hexdigest() != run.result_checksum
        ):
            raise ValueError("Result integrity check failed")


def verify_references(database: Database, storage: StorageBackend):
    with database.session() as session:
        verify_references_in(session, storage.read)


def create_online_database_snapshot(settings: Settings, destination: Path):
    """Opt-in PostgreSQL/database-object backup using one exported read-only snapshot."""
    destination = destination.resolve()
    root = settings.storage_root.resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Snapshot and live storage must be separate")
    database = Database(settings.database_url.get_secret_value())
    try:
        if settings.storage_backend != "database" or database.engine.dialect.name != "postgresql":
            raise ValueError("Online backup requires PostgreSQL with database object storage")
        with (
            database.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
            conn.begin(),
        ):
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            with Session(bind=conn) as session:
                if (
                    session.scalar(text("SELECT version_num FROM alembic_version"))
                    != database.revision
                ):
                    raise ValueError("Current migration required")
                verify_references_in(
                    session, lambda key: DatabaseStorageBackend.read_in(session, key)
                )
                snapshot = session.scalar(text("SELECT pg_export_snapshot()"))
                destination.mkdir(parents=True, exist_ok=False)
                (destination / "objects").mkdir()
                dump = destination / "database.dump"
                pg_command(database, "backup", dump, snapshot=snapshot)
        manifest = {
            "schema": 1,
            "database": "postgresql",
            "storage_backend": "database",
            "consistency": "postgres-exported-snapshot",
            "created_at": datetime.now(UTC).isoformat(),
            "files": {"database.dump": {"sha256": digest(dump), "size_bytes": dump.stat().st_size}},
        }
        (destination / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
        return manifest
    finally:
        database.engine.dispose()


def create_snapshot(settings: Settings, destination: Path, *, writers_stopped: bool = False):
    if not writers_stopped:
        raise ValueError("Stop all writers and acknowledge offline operation")
    destination = destination.resolve()
    root = settings.storage_root.resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Snapshot and live storage must be separate")
    database = Database(settings.database_url.get_secret_value())
    lease = ExecutorLease(database, root)
    try:
        lease.acquire()
        with FileLock(root / ".analysis.lock"), FileLock(root / ".write.lock"), database.write():
            with database.session() as session:
                active = session.scalar(
                    select(AnalysisRun.id).where(AnalysisRun.status == Status.RUNNING)
                )
                uploading = session.scalar(
                    select(Investigation.id).where(Investigation.status == Status.UPLOADING)
                )
                if active or uploading:
                    raise ValueError("Recover interrupted writes before backup")
                if session.scalar(select(StorageDeletion.key).limit(1)):
                    raise ValueError(
                        "Complete pending storage deletion before creating a new backup"
                    )
            verify_references(database, storage_for(database, settings))
            destination.mkdir(parents=True, exist_ok=False)
            (destination / "objects").mkdir()
            dialect = database.engine.dialect.name
            db_file = "database.sqlite3" if dialect == "sqlite" else "database.dump"
            if dialect == "sqlite":
                source_path = Path(database.engine.url.database).resolve()
                with (
                    sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source,
                    sqlite3.connect(destination / db_file) as target,
                ):
                    source.backup(target)
            else:
                pg_command(database, "backup", destination / db_file)
            paths = [destination / db_file]
            for path in sorted(root.glob("*.json")) if settings.storage_backend == "local" else []:
                if not re.fullmatch(r"[a-f0-9]{32}\.json", path.name) or path.is_symlink():
                    raise ValueError("Unexpected object in storage")
                target = destination / "objects" / path.name
                shutil.copyfile(path, target)
                paths.append(target)
            manifest = {
                "schema": 1,
                "database": dialect,
                "storage_backend": settings.storage_backend,
                "created_at": datetime.now(UTC).isoformat(),
                "files": {
                    p.relative_to(destination).as_posix(): {
                        "sha256": digest(p),
                        "size_bytes": p.stat().st_size,
                    }
                    for p in paths
                },
            }
            # Manifest is the completion marker; incomplete snapshots have none.
            (destination / "manifest.json").write_text(
                json.dumps(manifest, sort_keys=True, indent=2)
            )
            return manifest
    finally:
        lease.release()
        database.engine.dispose()


def validate_snapshot(source: Path) -> dict:
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("database") not in {"sqlite", "postgresql"}:
        raise ValueError("Unsupported snapshot")
    required = "database.sqlite3" if manifest["database"] == "sqlite" else "database.dump"
    if required not in manifest["files"]:
        raise ValueError("Snapshot database missing")
    for name, record in manifest["files"].items():
        if not re.fullmatch(r"(database\.(sqlite3|dump)|objects/[a-f0-9]{32}\.json)", name):
            raise ValueError("Unsafe snapshot path")
        path = source / name
        if (
            path.is_symlink()
            or path.parent.is_symlink()
            or not path.resolve().is_relative_to(source.resolve())
        ):
            raise ValueError("Unsafe snapshot location")
        if path.stat().st_size != record["size_bytes"] or digest(path) != record["sha256"]:
            raise ValueError("Snapshot checksum mismatch")
    return manifest


def restore_snapshot(settings: Settings, source: Path, *, writers_stopped: bool = False):
    if not writers_stopped:
        raise ValueError("Stop all writers and acknowledge offline operation")
    manifest = validate_snapshot(source)
    if manifest.get("storage_backend", "local") != settings.storage_backend:
        raise ValueError("Snapshot storage backend does not match target")
    root = settings.storage_root.resolve()
    if root.exists():
        raise ValueError("Restore requires a new storage directory")
    database = Database(settings.database_url.get_secret_value())
    try:
        dialect = database.engine.dialect.name
        if dialect != manifest["database"]:
            raise ValueError("Snapshot database dialect does not match target")
        if dialect == "sqlite":
            target_db = Path(database.engine.url.database).resolve()
            if target_db.exists():
                raise ValueError("Restore never overwrites an existing database")
        elif inspect(database.engine).get_table_names():
            raise ValueError("Restore requires an empty PostgreSQL database")
        root.mkdir(parents=True, exist_ok=False)
        # Restore objects first while offline, then metadata that references them.
        for name in manifest["files"]:
            if name.startswith("objects/"):
                with (
                    (root / Path(name).name).open("xb") as target,
                    (source / name).open("rb") as stream,
                ):
                    shutil.copyfileobj(stream, target)
        if dialect == "sqlite":
            target_db.parent.mkdir(parents=True, exist_ok=True)
            with target_db.open("xb") as target, (source / "database.sqlite3").open("rb") as stream:
                shutil.copyfileobj(stream, target)
        else:
            pg_command(database, "restore", source / "database.dump")
        verify_references(database, storage_for(database, settings))
        return {"status": "restored", "files": len(manifest["files"])}
    finally:
        database.engine.dispose()


def retention_report(settings: Settings):
    from ringsentinel.platform.deletion import retention_conditions

    database = Database(settings.database_url.get_secret_value())
    cutoff = datetime.now(UTC) - timedelta(days=settings.retention_days)
    try:
        with database.session() as session:
            ids = list(
                session.scalars(
                    select(Investigation.id).where(
                        *retention_conditions(cutoff),
                    )
                )
            )
        return {
            "policy_days": settings.retention_days,
            "eligible_investigation_ids": sorted(ids),
            "automatic_deletion": False,
        }
    finally:
        database.engine.dispose()


def apply_retention(settings: Settings, *, confirmed: bool = False, limit: int = 100):
    """Explicit operator action; never called by API or automatically by the scheduler."""
    from ringsentinel.platform.deletion import DeletionService, retention_conditions
    from ringsentinel.platform.errors import ProductError
    from ringsentinel.platform.service import InvestigationService, Principal

    if not confirmed:
        raise ValueError("Explicit confirmation of the configured retention policy is required")
    if not 1 <= limit <= 1000:
        raise ValueError("Retention batch must contain between 1 and 1000 cases")
    database = Database(settings.database_url.get_secret_value())
    cutoff = datetime.now(UTC) - timedelta(days=settings.retention_days)
    service = InvestigationService(database, storage_for(database, settings), settings)
    deleted, skipped = 0, 0
    try:
        with database.session() as session:
            cases = list(
                session.scalars(
                    select(Investigation)
                    .where(*retention_conditions(cutoff))
                    .order_by(Investigation.updated_at, Investigation.id)
                    .limit(limit)
                )
            )
        for case in cases:
            try:
                DeletionService(service).remove(
                    Principal(case.owner_id), case.id, case.name, older_than=cutoff
                )
                deleted += 1
            except ProductError as failure:
                if failure.code not in {"NOT_FOUND", "CONFLICT"}:
                    raise
                skipped += 1
        cleanup = DeletionService(service).cleanup()
        return {
            "deleted": deleted,
            "skipped_changed": skipped,
            "pending_storage_objects": cleanup["pending"],
            "policy_days": settings.retention_days,
        }
    finally:
        database.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["backup", "restore", "retention-report", "retention-delete"]
    )
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument("--online-database", action="store_true")
    parser.add_argument("--confirm-delete-expired", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        settings = Settings()
        if args.online_database and (args.action != "backup" or args.writers_stopped):
            parser.error("--online-database is only for backup without --writers-stopped")
        if args.action == "retention-report":
            result = retention_report(settings)
        elif args.action == "retention-delete":
            result = apply_retention(
                settings, confirmed=args.confirm_delete_expired, limit=args.limit
            )
        else:
            if not args.directory:
                parser.error("--directory is required")
            if args.online_database:
                result = create_online_database_snapshot(settings, args.directory)
            else:
                action = create_snapshot if args.action == "backup" else restore_snapshot
                result = action(settings, args.directory, writers_stopped=args.writers_stopped)
        print(json.dumps(result, sort_keys=True))
    except Exception:
        # No driver errors, credentials, paths or stack traces on the console.
        parser.exit(
            1,
            "Operation failed safely. Verify offline state, configuration, tools "
            "and snapshot integrity.\n",
        )


if __name__ == "__main__":
    main()
