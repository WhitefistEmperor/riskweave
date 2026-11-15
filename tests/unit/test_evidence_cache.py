"""Bounded, integrity-checked, failure-tolerant evidence cache primitives."""

import pytest

from ringsentinel.platform.evidence_cache import (
    EvidenceCache,
    MemoryBackend,
    RedisBackend,
    cache_key,
    evidence_cache_from_settings,
)
from ringsentinel.platform.settings import Settings


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_keys_bind_owner_run_checksum_kind_and_candidate():
    base = ("owner", "run", "a" * 64, "evidence", "c1")
    variants = {
        cache_key(*base),
        cache_key("other", *base[1:]),
        cache_key(base[0], "run2", *base[2:]),
        cache_key(*base[:2], "b" * 64, *base[3:]),
        cache_key(*base[:3], "candidate", base[4]),
        cache_key(*base[:4], "c2"),
        cache_key(*base, "question-hash"),
    }
    assert len(variants) == 7
    assert cache_key(*base) == cache_key(*base)
    # Analyst-owned identifiers never appear verbatim; only the run id namespaces keys.
    assert "owner" not in cache_key(*base) and "c1" not in cache_key(*base)


def test_memory_backend_enforces_ttl_entry_and_byte_limits():
    clock = Clock()
    backend = MemoryBackend(max_entries=2, max_bytes=10, clock=clock)
    backend.set("a", b"1234", 5)
    backend.set("b", b"1234", 5)
    assert backend.get("a") == b"1234"  # refreshes LRU position of "a"
    backend.set("c", b"12", 5)
    assert backend.get("b") is None and len(backend) == 2 and backend.evictions == 1
    backend.set("d", b"123456", 5)  # 4 + 2 + 6 > 10 bytes → evict oldest
    assert backend._bytes <= 10
    backend.set("huge", b"x" * 11, 5)
    assert backend.get("huge") is None
    clock.now += 6
    assert backend.get("d") is None and backend.get("c") is None


def test_hits_misses_integrity_and_prefix_invalidation():
    cache = EvidenceCache(MemoryBackend(max_entries=10, max_bytes=10_000), ttl_seconds=60)
    key = cache_key("o", "run-1", "a" * 64, "evidence", "c")
    loads = []
    assert cache.through(key, lambda: loads.append(1) or {"v": "€"}) == {"v": "€"}
    assert cache.through(key, lambda: loads.append(1) or {"v": "other"}) == {"v": "€"}
    assert loads == [1]
    # Tampered bytes are discarded and reloaded, never served.
    cache.backend.set(key, b"0" * 64 + b'\n{"v":"forged"}', 60)
    assert cache.get_json(key) == (False, None)
    assert cache.counters["integrity_discards"] == 1
    other = cache_key("o", "run-2", "a" * 64, "evidence", "c")
    cache.set_json(key, 1)
    cache.set_json(other, 2)
    cache.invalidate_runs(["run-1"])
    assert cache.get_json(key) == (False, None)
    assert cache.get_json(other) == (True, 2)
    stats = cache.stats()
    assert stats["backend"] == "MemoryBackend" and stats["invalidated"] == 1
    assert stats["hits"] == 2 and 0 < stats["hit_ratio"] < 1


def test_oversized_values_are_not_stored():
    cache = EvidenceCache(MemoryBackend(max_entries=10, max_bytes=10**6), max_value_bytes=1024)
    cache.set_json("k", "x" * 2000)
    assert cache.get_json("k") == (False, None) and cache.counters["skipped_large"] == 1


class BrokenRedis:
    def __init__(self):
        self.calls = 0

    def _fail(self, *_, **__):
        self.calls += 1
        raise ConnectionError("redis down")

    get = set = delete = _fail

    def scan_iter(self, **_):
        self._fail()


def test_backend_outage_degrades_to_loader_with_circuit_breaker():
    clock = Clock()
    client = BrokenRedis()
    cache = EvidenceCache(RedisBackend(client), breaker_seconds=30, clock=clock)
    assert cache.through("k", lambda: {"authoritative": True}) == {"authoritative": True}
    assert client.calls == 1 and cache.counters["errors"] == 1
    # Breaker open: no further backend calls, still correct results.
    for _ in range(5):
        assert cache.through("k", lambda: 7) == 7
    # The first store after the failed lookup is also bypassed.
    assert client.calls == 1 and cache.counters["bypassed"] == 11
    cache.invalidate_runs(["run"])  # never raises during erasure
    clock.now += 31
    assert cache.through("k", lambda: 8) == 8
    assert client.calls == 3


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex):
        assert ex > 0
        self.data[key] = value

    def scan_iter(self, match, count):
        prefix = match.rstrip("*")
        return [key for key in list(self.data) if key.startswith(prefix)]

    def delete(self, *keys):
        return sum(self.data.pop(key, None) is not None for key in keys)


def test_redis_backend_round_trip_and_invalidation():
    cache = EvidenceCache(RedisBackend(FakeRedis()))
    key = cache_key("o", "run-9", "c" * 64, "candidate", "x")
    cache.set_json(key, {"candidate_id": "x"})
    assert cache.get_json(key) == (True, {"candidate_id": "x"})
    cache.invalidate_runs(["run-9"])
    assert cache.get_json(key) == (False, None)


def test_settings_select_backend_and_validate_redis_urls():
    assert evidence_cache_from_settings(Settings(environment="test")).stats()["backend"] == (
        "MemoryBackend"
    )
    disabled = evidence_cache_from_settings(
        Settings(environment="test", evidence_cache_backend="disabled")
    )
    assert not disabled.enabled and disabled.through("k", lambda: 3) == 3
    with pytest.raises(ValueError, match="redis://"):
        Settings(environment="test", evidence_cache_backend="redis", evidence_cache_url="http://x")
    with pytest.raises(ValueError, match="TLS"):
        Settings(
            environment="production", evidence_cache_backend="redis", evidence_cache_url="redis://x"
        )
