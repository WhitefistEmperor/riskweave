import json

import pytest

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.backup import create_snapshot, restore_snapshot, retention_report
from ringsentinel.platform.database import Database
from ringsentinel.platform.jobs import LocalJobExecutor
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


@pytest.fixture
def saved(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'source.db'}",
        storage_root=tmp_path / "source-objects",
        jobs_enabled=False,
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    service = InvestigationService(db, LocalStorageBackend(settings.storage_root), settings)
    owner = Principal("backup-owner")
    inv = service.create(owner, "Restore me")
    payload = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    obj = service.attach(owner, inv.id, payload, "input.json", "application/json")
    run = service.start(owner, inv.id, obj.id, "original")
    service.claim()
    service.finish(run.id, {"rings": [], "verification": "unchanged"})
    yield service, owner, inv.id, run.id
    db.engine.dispose()


def test_real_offline_backup_restore_reopens_results_and_ownership(saved, tmp_path):
    service, owner, inv_id, run_id = saved
    destination = tmp_path / "snapshot"
    manifest = create_snapshot(service.settings, destination, writers_stopped=True)
    assert len(manifest["files"]) == 3
    target = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'restored.db'}",
        storage_root=tmp_path / "restored-objects",
        jobs_enabled=False,
    )
    assert restore_snapshot(target, destination, writers_stopped=True)["status"] == "restored"
    db = Database(target.database_url.get_secret_value())
    db.migrate()  # Restore contains the migration state; repeated migrate is safe.
    restored = InvestigationService(db, LocalStorageBackend(target.storage_root), target)
    try:
        assert restored.get(owner, inv_id).name == "Restore me"
        assert restored.result(owner, run_id) == service.result(owner, run_id)
        assert (
            restored.run(owner, run_id).result_checksum
            == service.run(owner, run_id).result_checksum
        )
        assert restored.list(Principal("other")) == []
        assert retention_report(target)["automatic_deletion"] is False
    finally:
        db.engine.dispose()
    with pytest.raises(ValueError, match="new storage"):
        restore_snapshot(target, destination, writers_stopped=True)


def test_backup_refuses_online_unacknowledged_overwrite_and_corruption(saved, tmp_path):
    service, _, _, _ = saved
    destination = tmp_path / "snapshot"
    with pytest.raises(ValueError, match="Stop all writers"):
        create_snapshot(service.settings, destination)
    executor = LocalJobExecutor(service)
    executor.start()
    try:
        with pytest.raises(RuntimeError):
            create_snapshot(service.settings, destination, writers_stopped=True)
    finally:
        executor.stop()
    create_snapshot(service.settings, destination, writers_stopped=True)
    with pytest.raises(FileExistsError):
        create_snapshot(service.settings, destination, writers_stopped=True)
    manifest = json.loads((destination / "manifest.json").read_text())
    name = next(k for k in manifest["files"] if k.startswith("objects/"))
    (destination / name).write_bytes(b"corrupt")
    target = Settings(
        database_url=f"sqlite:///{tmp_path / 'new.db'}", storage_root=tmp_path / "new"
    )
    with pytest.raises(ValueError, match="checksum"):
        restore_snapshot(target, destination, writers_stopped=True)
    assert not target.storage_root.exists()


def test_restore_rejects_manifest_traversal_before_writing(saved, tmp_path):
    service, _, _, _ = saved
    destination = tmp_path / "snapshot"
    create_snapshot(service.settings, destination, writers_stopped=True)
    path = destination / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"]["../outside"] = {"sha256": "x", "size_bytes": 1}
    path.write_text(json.dumps(manifest))
    target = Settings(
        database_url=f"sqlite:///{tmp_path / 'new.db'}", storage_root=tmp_path / "new"
    )
    with pytest.raises(ValueError, match="Unsafe snapshot path"):
        restore_snapshot(target, destination, writers_stopped=True)
    assert not target.storage_root.exists()
