"""Opaque object keys, exclusive writes, and storage-independent references."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.locking import FileLock


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    checksum: str


class StorageBackend(Protocol):
    def save(self, content: bytes) -> StoredObject: ...
    def read(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def reference(self, key: str) -> str: ...
    def ready(self) -> bool: ...


class LocalStorageBackend:
    def __init__(self, root: Path, limit_bytes: int = 2_000_000_000):
        self.root = root.resolve()
        self.limit_bytes = limit_bytes

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}\.json", key):
            raise ValueError("Invalid storage key")
        path = self.root / key
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError("Invalid storage location")
        return path

    def save(self, content: bytes) -> StoredObject:
        self.root.mkdir(parents=True, exist_ok=True)
        # Serializes byte-budget admission across API and child processes.
        try:
            with FileLock(self.root / ".write.lock"):
                used = sum(p.stat().st_size for p in self.root.glob("*.json") if p.is_file())
                if used + len(content) > self.limit_bytes:
                    raise ProductError("QUOTA_EXCEEDED")
                return self._save(content)
        except RuntimeError:
            raise ProductError("CONFLICT") from None

    def _save(self, content: bytes) -> StoredObject:
        key = f"{uuid4().hex}.json"
        path = self._path(key)
        # If exclusive creation fails, this caller does not own the existing object.
        stream = path.open("xb")
        try:
            with stream:
                stream.write(content)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return StoredObject(key, len(content), hashlib.sha256(content).hexdigest())

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def reference(self, key: str) -> str:
        self._path(key)
        return f"object:{key}"

    def ready(self) -> bool:
        try:
            obj = self.save(b"{}")
            valid = self.read(obj.key) == b"{}"
            self.delete(obj.key)
            return valid
        except (OSError, ProductError):
            return False
