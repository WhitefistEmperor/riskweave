"""A saved (prebuilt) demo runtime must answer exactly like a freshly trained one."""

import json
from pathlib import Path

import pytest

from ringsentinel.api import runtime as runtime_module
from ringsentinel.api.runtime import (
    PREBUILT_ENV,
    DemoRuntime,
    get_demo_runtime,
    load_prebuilt_runtime,
    save_prebuilt_runtime,
)


def dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


@pytest.fixture(scope="module")
def fresh() -> DemoRuntime:
    return DemoRuntime()


@pytest.fixture(scope="module")
def saved(fresh: DemoRuntime, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return save_prebuilt_runtime(tmp_path_factory.mktemp("prebuilt") / "runtime.pkl", fresh)


def test_loaded_runtime_answers_identically(fresh: DemoRuntime, saved: Path) -> None:
    loaded = load_prebuilt_runtime(saved)
    for name in ("overview", "benchmark", "list_candidates", "simulation", "hard_negatives"):
        assert dump(getattr(loaded, name)()) == dump(getattr(fresh, name)()), name
    first = fresh.list_candidates()[0]["candidate_id"]
    for name in ("candidate", "candidate_graph", "candidate_timeline", "candidate_evidence"):
        assert dump(getattr(loaded, name)(first)) == dump(getattr(fresh, name)(first)), name
    assert dump(loaded.snapshot(300, None)) == dump(fresh.snapshot(300, None))


def test_loading_does_not_retrain(saved: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("training ran although a prebuilt runtime was loaded")

    monkeypatch.setattr(runtime_module, "_prepare", forbidden)
    assert load_prebuilt_runtime(saved).overview()["candidate_rings"] > 0


def test_mismatched_file_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pkl"
    import pickle

    bad.write_bytes(pickle.dumps({"format": 999, "seeds": (), "transactions": 0, "state": {}}))
    with pytest.raises(ValueError):
        load_prebuilt_runtime(bad)


def test_unusable_or_missing_file_falls_back_to_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.pkl"
    broken.write_bytes(b"not a pickle")
    monkeypatch.setenv(PREBUILT_ENV, str(broken))
    get_demo_runtime.cache_clear()
    try:
        assert isinstance(get_demo_runtime(), DemoRuntime)
        monkeypatch.setenv(PREBUILT_ENV, str(tmp_path / "does-not-exist.pkl"))
        get_demo_runtime.cache_clear()
        assert isinstance(get_demo_runtime(), DemoRuntime)
    finally:
        get_demo_runtime.cache_clear()
