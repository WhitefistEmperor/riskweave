"""Offline, checksummed snapshots. Never overwrites a database, storage root or snapshot.

Stop every application writer before use. An explicit operator acknowledgement is required;
executor/child locks also reject an accidentally running supported executor.
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

from sqlalchemy import inspect, select

from ringsentinel.platform.database import Database
from ringsentinel.platform.locking import ExecutorLease, FileLock
from ringsentinel.platform.models import AnalysisRun, Artifact, Investigation, Status
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pg_command(database: Database, action: str, path: Path):
    """Use standard PostgreSQL tools, no shell and no passwords in argv or output."""
    url = database.engine.url
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


def verify_references(database: Database, storage: LocalStorageBackend):
    with database.session() as session:
        for obj in session.scalars(select(Artifact)):
            path = storage._path(obj.storage_key)
            if path.stat().st_size != obj.size_bytes or digest(path) != obj.checksum:
                raise ValueError("Artifact integrity check failed")
        for run in session.scalars(
            select(AnalysisRun).where(AnalysisRun.status == Status.COMPLETED)
        ):
            if (
                not run.result_reference
                or digest(storage._path(run.result_reference)) != run.result_checksum
            ):
                raise ValueError("Result integrity check failed")


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
        with FileLock(root / ".analysis.lock"), FileLock(root / ".write.lock"):
            with database.session() as session:
                active = session.scalar(
                    select(AnalysisRun.id).where(AnalysisRun.status == Status.RUNNING)
                )
                uploading = session.scalar(
                    select(Investigation.id).where(Investigation.status == Status.UPLOADING)
                )
                if active or uploading:
                    raise ValueError("Recover interrupted writes before backup")
            verify_references(database, LocalStorageBackend(root))
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
            for path in sorted(root.glob("*.json")):
                if not re.fullmatch(r"[a-f0-9]{32}\.json", path.name) or path.is_symlink():
                    raise ValueError("Unexpected object in storage")
                target = destination / "objects" / path.name
                shutil.copyfile(path, target)
                paths.append(target)
            manifest = {
                "schema": 1,
                "database": dialect,
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
        verify_references(database, LocalStorageBackend(root))
        return {"status": "restored", "files": len(manifest["files"])}
    finally:
        database.engine.dispose()


def retention_report(settings: Settings):
    database = Database(settings.database_url.get_secret_value())
    cutoff = datetime.now(UTC) - timedelta(days=settings.retention_days)
    try:
        with database.session() as session:
            ids = list(
                session.scalars(
                    select(Investigation.id).where(
                        Investigation.updated_at < cutoff,
                        Investigation.status.not_in(
                            [Status.RUNNING, Status.QUEUED, Status.UPLOADING]
                        ),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore", "retention-report"])
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    try:
        settings = Settings()
        if args.action == "retention-report":
            result = retention_report(settings)
        else:
            if not args.directory:
                parser.error("--directory is required")
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
