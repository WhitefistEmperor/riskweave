"""OS-released local locks and a PostgreSQL single-executor advisory lock.

Local filesystems only; do not use NFS/SMB for the supported single-host topology.
Lock files are intentionally never unlinked (unlinking permits split lock ownership).
"""

import os
from pathlib import Path

from sqlalchemy import text


class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.stream = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise RuntimeError("Unsafe lock location")
        stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if self.path.stat().st_size == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise RuntimeError("Resource already owned by another process") from None
        self.stream = stream
        return self

    def release(self):
        if self.stream:
            self.stream.close()
            self.stream = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.release()


class ExecutorLease:
    def __init__(self, database, storage_root: Path):
        self.database = database
        self.connection = None
        self.file = None
        self.storage_lock = FileLock(storage_root / ".executor.lock")

    def acquire(self):
        try:
            self.storage_lock.acquire()
            if self.database.engine.dialect.name == "postgresql":
                self.connection = self.database.engine.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                )
                if not self.connection.scalar(text("SELECT pg_try_advisory_lock(593001)")):
                    raise RuntimeError("Database executor already owned")
            else:
                path = Path(self.database.engine.url.database).resolve()
                self.file = FileLock(path.with_name(path.name + ".executor.lock")).acquire()
        except Exception:
            self.release()
            raise RuntimeError("Single executor ownership could not be acquired") from None

    def check(self):
        if self.connection is not None:
            # A reconnect must never silently recreate a lost session lock.
            if self.connection.invalidated:
                raise RuntimeError("Executor database session lost")
            self.connection.execute(text("SELECT 1"))

    def release(self):
        if self.connection is not None:
            try:
                if not self.connection.invalidated:
                    self.connection.execute(text("SELECT pg_advisory_unlock(593001)"))
            finally:
                self.connection.close()
                self.connection = None
        if self.file:
            self.file.release()
        self.storage_lock.release()
