"""Owner-scoped immutable evidence and answer cache.

Stored result bytes remain authoritative. A cache entry only skips re-reading and
re-verifying an immutable section that the same owner has already been authorized for:

- Every lookup happens *after* the database ownership/status check for that request.
- Keys bind owner, run, the run's result SHA-256, entry kind, candidate and a schema
  version, so a different owner, a re-run or a changed result can never hit an entry.
- Values carry their own SHA-256 and are re-verified on every hit; a mismatch is
  discarded and treated as a miss.
- Any backend failure (for example Redis being unreachable) degrades to a miss and opens
  a short circuit breaker. The cache is never required for inference or evidence.
- Investigation deletion purges every entry of the deleted runs.
- Only values that passed storage checksum verification are cached. Because result bytes
  are immutable, later storage corruption is detected on the next uncached read (at most
  one TTL later), not on a cache hit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import Any, Protocol

logger = logging.getLogger("ringsentinel.cache")

CACHE_VERSION = "v1"
KEY_PREFIX = f"ringsentinel:evidence:{CACHE_VERSION}"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def cache_key(
    owner_id: str, run_id: str, result_checksum: str, kind: str, candidate_id: str, extra: str = ""
) -> str:
    """Build a namespaced key. Run id stays readable so deletion can purge by run."""
    scope = json.dumps(
        [owner_id, result_checksum, kind, candidate_id, extra], separators=(",", ":")
    ).encode()
    return f"{KEY_PREFIX}:{run_id}:{_digest(scope)}"


def run_prefix(run_id: str) -> str:
    return f"{KEY_PREFIX}:{run_id}:"


class CacheBackend(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def set(self, key: str, value: bytes, ttl_seconds: int) -> None: ...

    def delete_prefix(self, prefix: str) -> int: ...


class MemoryBackend:
    """Bounded per-process LRU with TTL, entry and byte limits."""

    def __init__(
        self,
        *,
        max_entries: int,
        max_bytes: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_entries, self.max_bytes, self.clock = max_entries, max_bytes, clock
        self._items: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()
        self.evictions = 0

    def _drop(self, key: str) -> None:
        _, value = self._items.pop(key)
        self._bytes -= len(value)

    def get(self, key: str) -> bytes | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            if item[0] <= self.clock():
                self._drop(key)
                return None
            self._items.move_to_end(key)
            return item[1]

    def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        if len(value) > self.max_bytes:
            return
        with self._lock:
            if key in self._items:
                self._drop(key)
            self._items[key] = (self.clock() + ttl_seconds, value)
            self._bytes += len(value)
            while len(self._items) > self.max_entries or self._bytes > self.max_bytes:
                self._drop(next(iter(self._items)))
                self.evictions += 1

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._items if key.startswith(prefix)]
            for key in keys:
                self._drop(key)
            return len(keys)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


class RedisBackend:
    """Shared cache for multi-process hosting. Requires the optional ``redis`` package."""

    def __init__(self, client: Any) -> None:
        self.client = client

    @classmethod
    def from_url(cls, url: str, timeout_seconds: float) -> RedisBackend:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as error:  # pragma: no cover - depends on optional install
            message = "Redis evidence cache requires the optional 'redis' package"
            raise ValueError(message) from error
        return cls(
            redis.Redis.from_url(
                url,
                socket_timeout=timeout_seconds,
                socket_connect_timeout=timeout_seconds,
                retry_on_timeout=False,
            )
        )

    def get(self, key: str) -> bytes | None:
        return self.client.get(key)

    def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self.client.set(key, value, ex=ttl_seconds)

    def delete_prefix(self, prefix: str) -> int:
        removed = 0
        batch: list[Any] = []
        for key in self.client.scan_iter(match=f"{prefix}*", count=500):
            batch.append(key)
            if len(batch) >= 500:
                removed += self.client.delete(*batch)
                batch.clear()
        if batch:
            removed += self.client.delete(*batch)
        return removed


class EvidenceCache:
    """Integrity-checked, failure-tolerant facade with measured counters."""

    def __init__(
        self,
        backend: CacheBackend | None,
        *,
        ttl_seconds: int = 300,
        max_value_bytes: int = 4_000_000,
        breaker_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.backend = backend
        self.ttl_seconds = ttl_seconds
        self.max_value_bytes = max_value_bytes
        self.breaker_seconds = breaker_seconds
        self.clock = clock
        self._open_until = 0.0
        self._lock = threading.Lock()
        self.counters = {
            "hits": 0,
            "misses": 0,
            "stores": 0,
            "skipped_large": 0,
            "integrity_discards": 0,
            "errors": 0,
            "bypassed": 0,
            "invalidated": 0,
        }

    @property
    def enabled(self) -> bool:
        return self.backend is not None

    def _count(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] += amount

    def _available(self) -> bool:
        if self.backend is None:
            return False
        if self.clock() < self._open_until:
            self._count("bypassed")
            return False
        return True

    def _failed(self, operation: str, error: Exception) -> None:
        self._count("errors")
        self._open_until = self.clock() + self.breaker_seconds
        # Never log keys or values: they are derived from analyst-owned data.
        logger.warning(
            json.dumps(
                {
                    "event": "evidence_cache_unavailable",
                    "operation": operation,
                    "error_type": type(error).__name__,
                }
            )
        )

    def get_json(self, key: str) -> tuple[bool, Any]:
        if not self._available():
            return False, None
        try:
            raw = self.backend.get(key)  # type: ignore[union-attr]
        except Exception as error:
            self._failed("get", error)
            return False, None
        if raw is None:
            self._count("misses")
            return False, None
        try:
            checksum, _, body = bytes(raw).partition(b"\n")
            if _digest(body) != checksum.decode():
                raise ValueError("checksum")
            value = json.loads(body)
        except Exception:
            self._count("integrity_discards")
            self._count("misses")
            return False, None
        self._count("hits")
        return True, value

    def set_json(self, key: str, value: Any) -> None:
        if not self._available():
            return
        body = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
        if len(body) > self.max_value_bytes:
            self._count("skipped_large")
            return
        try:
            self.backend.set(  # type: ignore[union-attr]
                key, _digest(body).encode() + b"\n" + body, self.ttl_seconds
            )
        except Exception as error:
            self._failed("set", error)
            return
        self._count("stores")

    def through(self, key: str, load: Callable[[], Any]) -> Any:
        hit, value = self.get_json(key)
        if hit:
            return value
        value = load()
        self.set_json(key, value)
        return value

    def invalidate_runs(self, run_ids: Iterable[str]) -> None:
        if self.backend is None:
            return
        for run_id in run_ids:
            try:
                self._count("invalidated", self.backend.delete_prefix(run_prefix(run_id)))
            except Exception as error:
                # Entries are unreachable anyway (ownership check fails for deleted runs)
                # and expire by TTL; record the failure without blocking erasure.
                self._failed("invalidate", error)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self.counters)
        lookups = counters["hits"] + counters["misses"]
        return {
            "backend": type(self.backend).__name__ if self.backend is not None else "disabled",
            "hit_ratio": round(counters["hits"] / lookups, 4) if lookups else None,
            **counters,
        }


def evidence_cache_from_settings(settings: Any) -> EvidenceCache:
    backend: CacheBackend | None
    if settings.evidence_cache_backend == "disabled":
        backend = None
    elif settings.evidence_cache_backend == "redis":
        backend = RedisBackend.from_url(
            settings.evidence_cache_url.get_secret_value(),
            settings.evidence_cache_timeout_seconds,
        )
    else:
        backend = MemoryBackend(
            max_entries=settings.evidence_cache_max_entries,
            max_bytes=settings.evidence_cache_max_bytes,
        )
    return EvidenceCache(
        backend,
        ttl_seconds=settings.evidence_cache_ttl_seconds,
        max_value_bytes=settings.evidence_cache_max_value_bytes,
    )
