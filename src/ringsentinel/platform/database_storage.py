"""Private database object storage with atomic quota admission and case erasure."""

import hashlib
import re
from uuid import uuid4

from sqlalchemy import delete, func, select

from ringsentinel.platform.database import Database
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import AnalysisRun, Artifact, Status, StoredBlob
from ringsentinel.platform.storage import StoredObject


def valid_key(key: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{32}\.json", key):
        raise ValueError("Invalid storage key")


class DatabaseStorageBackend:
    def __init__(self, database: Database, limit_bytes: int):
        self.database, self.limit_bytes = database, limit_bytes

    def save_in(self, session, content: bytes) -> StoredObject:
        # Caller holds Database.write(); admission and bytes commit together.
        used = session.scalar(select(func.coalesce(func.sum(StoredBlob.size_bytes), 0)))
        if used + len(content) > self.limit_bytes:
            raise ProductError("QUOTA_EXCEEDED")
        obj = StoredObject(f"{uuid4().hex}.json", len(content), hashlib.sha256(content).hexdigest())
        session.add(
            StoredBlob(
                key=obj.key, content=content, size_bytes=obj.size_bytes, checksum=obj.checksum
            )
        )
        session.flush()
        return obj

    def save(self, content: bytes) -> StoredObject:
        with self.database.write() as session:
            return self.save_in(session, content)

    @staticmethod
    def read_in(session, key: str) -> bytes:
        valid_key(key)
        obj = session.get(StoredBlob, key)
        if obj is None:
            raise FileNotFoundError("Stored object missing")
        if (
            len(obj.content) != obj.size_bytes
            or hashlib.sha256(obj.content).hexdigest() != obj.checksum
        ):
            raise ProductError("INTERNAL_ERROR")
        return obj.content

    def read(self, key: str) -> bytes:
        with self.database.session() as session:
            return self.read_in(session, key)

    def exists(self, key: str) -> bool:
        valid_key(key)
        with self.database.session() as session:
            return session.scalar(select(StoredBlob.key).where(StoredBlob.key == key)) is not None

    @staticmethod
    def delete_in(session, key: str) -> None:
        valid_key(key)
        session.execute(delete(StoredBlob).where(StoredBlob.key == key))

    def delete(self, key: str) -> None:
        with self.database.write() as session:
            self.delete_in(session, key)

    def reference(self, key: str) -> str:
        valid_key(key)
        return f"object:{key}"

    def ready(self) -> bool:
        try:
            with self.database.write() as session:
                missing_input = session.scalar(
                    select(Artifact.id)
                    .outerjoin(StoredBlob, Artifact.storage_key == StoredBlob.key)
                    .where(StoredBlob.key.is_(None))
                    .limit(1)
                )
                missing_result = session.scalar(
                    select(AnalysisRun.id)
                    .outerjoin(StoredBlob, AnalysisRun.result_reference == StoredBlob.key)
                    .where(AnalysisRun.status == Status.COMPLETED, StoredBlob.key.is_(None))
                    .limit(1)
                )
                if missing_input or missing_result:
                    return False
                obj = self.save_in(session, b"{}")
                valid = self.read_in(session, obj.key) == b"{}"
                self.delete_in(session, obj.key)
                return valid
        except Exception:
            return False


def storage_for(database: Database, settings):
    if settings.storage_backend == "database":
        return DatabaseStorageBackend(database, settings.storage_limit_bytes)
    from ringsentinel.platform.storage import LocalStorageBackend

    return LocalStorageBackend(settings.storage_root, settings.storage_limit_bytes)


def import_local(settings, *, writers_stopped: bool = False) -> dict:
    """Copy verified existing references atomically without renaming or removing sources."""
    if not writers_stopped or settings.storage_backend != "database":
        raise ValueError("Stop writers and select database storage before importing")
    from ringsentinel.platform.locking import ExecutorLease, FileLock
    from ringsentinel.platform.storage import LocalStorageBackend

    database = Database(settings.database_url.get_secret_value())
    root = settings.storage_root.resolve()
    lease = ExecutorLease(database, root)
    copied = 0
    try:
        lease.acquire()
        with (
            FileLock(root / ".analysis.lock"),
            FileLock(root / ".write.lock"),
            database.write() as session,
        ):
            if session.scalar(
                select(AnalysisRun.id)
                .where(AnalysisRun.status.in_([Status.RUNNING, Status.QUEUED]))
                .limit(1)
            ):
                raise ValueError("Complete or recover active runs before import")
            from ringsentinel.platform.models import Investigation, StorageDeletion

            if session.scalar(
                select(Investigation.id).where(Investigation.status == Status.UPLOADING).limit(1)
            ) or session.scalar(select(StorageDeletion.key).limit(1)):
                raise ValueError("Complete upload and deletion work before import")
            source = LocalStorageBackend(root)
            references = {}
            for artifact in session.scalars(select(Artifact)):
                references[artifact.storage_key] = (artifact.checksum, artifact.size_bytes)
            for run in session.scalars(
                select(AnalysisRun).where(AnalysisRun.status == Status.COMPLETED)
            ):
                if not run.result_reference or not run.result_checksum:
                    raise ValueError("Completed run has no result reference")
                previous = references.get(run.result_reference)
                if previous and previous[0] != run.result_checksum:
                    raise ValueError("Conflicting storage references")
                references[run.result_reference] = (run.result_checksum, None)
            used = session.scalar(select(func.coalesce(func.sum(StoredBlob.size_bytes), 0)))
            for key, (checksum, size) in sorted(references.items()):
                valid_key(key)
                existing = session.get(StoredBlob, key)
                if existing:
                    content = DatabaseStorageBackend.read_in(session, key)
                else:
                    content = source.read(key)
                if hashlib.sha256(content).hexdigest() != checksum or (
                    size is not None and len(content) != size
                ):
                    raise ValueError("Source object integrity check failed")
                if existing:
                    continue
                if used + len(content) > settings.storage_limit_bytes:
                    raise ProductError("QUOTA_EXCEEDED")
                session.add(
                    StoredBlob(key=key, content=content, size_bytes=len(content), checksum=checksum)
                )
                used += len(content)
                copied += 1
        return {"copied": copied, "source_objects_removed": False}
    finally:
        lease.release()
        database.engine.dispose()


def main():
    import argparse
    import json

    from ringsentinel.platform.settings import Settings

    parser = argparse.ArgumentParser(
        description="Import verified local case files into database storage"
    )
    parser.add_argument("--confirm-writers-stopped", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(import_local(Settings(), writers_stopped=args.confirm_writers_stopped)))
    except Exception:
        parser.exit(
            1,
            "Import unavailable; no copy committed. Check configuration and private diagnostics.\n",
        )


if __name__ == "__main__":
    main()
