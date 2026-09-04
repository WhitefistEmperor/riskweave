"""Opaque object keys, exclusive writes, and storage-independent references."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4


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
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}\.json", key):
            raise ValueError("Invalid storage key")
        path = self.root / key
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError("Invalid storage location")
        return path

    def save(self, content: bytes) -> StoredObject:
        self.root.mkdir(parents=True, exist_ok=True)
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
        except OSError:
            return False
