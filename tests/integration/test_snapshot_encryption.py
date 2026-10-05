"""Actual standard age envelopes; generated snapshots only, never operator keys or real cases."""

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.backup import create_snapshot, restore_snapshot, validate_snapshot
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.snapshot_encryption import seal, unseal


@pytest.fixture(params=["local", "database"])
def encrypted_control(tmp_path, request):
    binary = os.environ.get("RINGSENTINEL_TEST_AGE") or shutil.which("age")
    if not binary:
        pytest.skip("Configure a trusted age executable for the encryption drill")
    binary = str(Path(binary).resolve())
    keygen = str(Path(binary).with_name("age-keygen.exe" if os.name == "nt" else "age-keygen"))
    identity = tmp_path / "identity.txt"
    subprocess.run(
        [keygen, "--output", str(identity)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    public = subprocess.check_output([keygen, "-y", str(identity)], text=True).strip()
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        storage_backend=request.param,
        database_url=f"sqlite:///{tmp_path / 'source.db'}",
        storage_root=tmp_path / "objects",
    )
    database = Database(settings.database_url.get_secret_value())
    database.migrate()
    # Generated persisted bytes and result exercise both storage modes without model training.
    service = InvestigationService(database, storage_for(database, settings), settings)
    owner = Principal("encryption-control-owner")
    case = service.create(owner, "Generated encrypted snapshot")
    payload = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    artifact = service.attach(owner, case.id, payload, "generated.json", "application/json")
    run = service.start(owner, case.id, artifact.id, "encryption-drill")
    service.claim()
    service.finish(run.id, {"rings": [], "verification": "generated-encryption-fixture"})
    source = tmp_path / "snapshot"
    create_snapshot(settings, source, writers_stopped=True)
    yield (
        binary,
        identity,
        public,
        source,
        settings,
        owner,
        case.id,
        run.id,
        artifact.storage_key,
        payload,
    )
    database.engine.dispose()


def test_actual_age_roundtrip_and_database_restore(encrypted_control, tmp_path):
    binary, identity, public, source, settings, owner, case_id, run_id, storage_key, payload = (
        encrypted_control
    )
    output = tmp_path / "snapshot.age"
    sealed = seal(source, output, public, binary=binary)
    assert sealed["status"] == "encrypted" and sealed["size_bytes"] > 0
    decoded = tmp_path / "decoded"
    assert unseal(output, decoded, identity, binary=binary)["status"] == "snapshot_unsealed"
    assert validate_snapshot(decoded) == validate_snapshot(source)
    target = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'restore.db'}",
        storage_root=tmp_path / "restore-objects",
        storage_backend=settings.storage_backend,
    )
    assert restore_snapshot(target, decoded, writers_stopped=True)["status"] == "restored"
    db = Database(target.database_url.get_secret_value())
    assert (
        InvestigationService(db, storage_for(db, target), target).get(owner, case_id).name
        == "Generated encrypted snapshot"
    )
    restored = InvestigationService(db, storage_for(db, target), target)
    assert restored.storage.read(storage_key) == payload
    assert restored.result(owner, run_id) == {
        "rings": [],
        "verification": "generated-encryption-fixture",
    }
    assert restored.list(Principal("different-owner")) == []
    db.engine.dispose()


def test_wrong_key_and_ciphertext_tamper_never_create_decoded_destination(
    encrypted_control, tmp_path
):
    binary, identity, public, source, *_ = encrypted_control
    ciphertext = tmp_path / "snapshot.age"
    seal(source, ciphertext, public, binary=binary)
    wrong = tmp_path / "wrong.txt"
    keygen = Path(binary).with_name("age-keygen.exe" if os.name == "nt" else "age-keygen")
    subprocess.run([str(keygen), "-o", str(wrong)], check=True, stderr=subprocess.DEVNULL)
    with pytest.raises(ValueError):
        unseal(ciphertext, tmp_path / "wrong-output", wrong, binary=binary)
    assert not (tmp_path / "wrong-output").exists()
    content = bytearray(ciphertext.read_bytes())
    content[-1] ^= 1
    ciphertext.write_bytes(content)
    with pytest.raises(ValueError):
        unseal(ciphertext, tmp_path / "corrupt-output", identity, binary=binary)
    assert not (tmp_path / "corrupt-output").exists()


def test_existing_outputs_and_failed_tool_preserve_originals(encrypted_control, tmp_path):
    binary, identity, public, source, *_ = encrypted_control
    output = tmp_path / "snapshot.age"
    output.write_bytes(b"KEEP")
    with pytest.raises(ValueError):
        seal(source, output, public, binary=binary)
    assert output.read_bytes() == b"KEEP"
    missing = tmp_path / "tool-failed.age"
    with pytest.raises(ValueError):
        seal(source, missing, public, binary=tmp_path / "missing-age")
    assert not missing.exists()
    output.unlink()
    seal(source, output, public, binary=binary)
    with pytest.raises(ValueError):
        unseal(output, source, identity, binary=binary)
    validate_snapshot(source)


@pytest.mark.parametrize("kind", ["traversal", "symlink", "duplicate", "undeclared"])
def test_encrypted_unsafe_archives_fail_before_any_outside_write(encrypted_control, tmp_path, kind):
    binary, identity, public, source, *_ = encrypted_control
    plain = tmp_path / "malicious.tar"
    with tarfile.open(plain, "w") as tar:
        if kind in ("duplicate", "undeclared"):
            for name in ("manifest.json", "database.sqlite3"):
                tar.add(source / name, arcname=name)
        info = tarfile.TarInfo(
            {
                "traversal": "../escape",
                "symlink": "database.sqlite3",
                "duplicate": "database.sqlite3",
                "undeclared": "objects/" + "a" * 32 + ".json",
            }[kind]
        )
        info.size = 1
        if kind == "symlink":
            info.type = tarfile.SYMTYPE
            info.linkname = "../escape"
            info.size = 0
        tar.addfile(info, io.BytesIO(b"x"))
    ciphertext = tmp_path / "malicious.age"
    with plain.open("rb") as stdin, ciphertext.open("xb") as stdout:
        subprocess.run(
            [binary, "-r", public],
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    with pytest.raises(ValueError):
        unseal(ciphertext, tmp_path / "decoded-malicious", identity, binary=binary)
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "decoded-malicious" / "manifest.json").exists()


def test_cli_failure_does_not_echo_private_identity_or_paths(tmp_path, monkeypatch, capsys):
    from ringsentinel.platform import snapshot_encryption

    private = tmp_path / "PRIVATE IDENTITY.txt"
    private.write_text("PRIVATE INVALID KEY")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "envelope",
            "unseal",
            "--source",
            str(private),
            "--output",
            str(tmp_path / "new"),
            "--identity",
            str(private),
        ],
    )
    with pytest.raises(SystemExit) as error:
        snapshot_encryption.main()
    assert error.value.code == 2
    output = capsys.readouterr().out
    assert json.loads(output)["code"] == "SNAPSHOT_ENVELOPE_FAILED"
    assert "PRIVATE" not in output and str(tmp_path) not in output
