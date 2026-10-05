"""Isolated real pg_dump/pg_restore drill. Never accepts a non-CI database target."""

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.backup import create_snapshot, restore_snapshot
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.operations import report
from ringsentinel.platform.result_transport import ResultTransport
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.snapshot_encryption import seal, unseal


@pytest.fixture
def databases():
    configured = os.getenv("RINGSENTINEL_TEST_POSTGRES_URL")
    if not configured:
        pytest.skip("Dedicated PostgreSQL backup drill is configured in Linux CI")
    url = make_url(configured)
    if (
        url.host != "127.0.0.1"
        or url.username != "riskweave_backup_ci"
        or url.database != "postgres"
    ):
        pytest.fail("Backup drill requires its isolated loopback CI administrator")
    names = ["riskweave_drill_" + uuid4().hex for _ in range(2)]
    created = []
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            yield [url.set(database=name).render_as_string(hide_password=False) for name in names]
        finally:
            for name in created:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.mark.parametrize("backend", ["local", "database"])
def test_postgres_snapshot_reopens_bytes_owner_and_migration_state(
    databases, backend, tmp_path, monkeypatch
):
    source = Settings(
        environment="test",
        database_url=databases[0],
        storage_root=tmp_path / "source",
        storage_backend=backend,
        jobs_enabled=False,
    )
    target = Settings(
        environment="test",
        database_url=databases[1],
        storage_root=tmp_path / "target",
        storage_backend=backend,
        jobs_enabled=False,
    )
    source_db = Database(databases[0])
    target_db = Database(databases[1])
    try:
        source_db.migrate()
        service = InvestigationService(source_db, storage_for(source_db, source), source)
        owner = Principal("ci-backup-owner")
        case = service.create(owner, "Generated restore fixture")
        payload = (
            SyntheticPaymentGenerator(GenerationConfig(transactions=100))
            .generate()
            .model_dump_json()
            .encode()
        )
        artifact = service.attach(owner, case.id, payload, "input.json", "application/json")
        run = service.start(owner, case.id, artifact.id, "backup-drill")
        service.claim()
        service.finish(
            run.id,
            {
                "rings": [{"candidate": {"candidate_id": "restore-candidate"}}],
                "verification": "generated-lifecycle-fixture",
                "transport_fixture": "x" * 2_000_032,
            },
        )
        from ringsentinel.platform.models import ReviewDisposition
        from ringsentinel.platform.reviews import ReviewService

        ReviewService(service).save(
            owner,
            run.id,
            "restore-candidate",
            ReviewDisposition.ESCALATED,
            "Generated restore review",
            0,
            "restore-review",
        )
        checksum = service.run(owner, run.id).result_checksum
        snapshot = tmp_path / "snapshot"
        create_snapshot(source, snapshot, writers_stopped=True)
        age = os.getenv("RINGSENTINEL_TEST_AGE")
        if age:
            identity = tmp_path / "drill-identity.txt"
            keygen = str(Path(age).with_name("age-keygen.exe" if os.name == "nt" else "age-keygen"))
            subprocess.run([keygen, "-o", str(identity)], check=True, stderr=subprocess.DEVNULL)
            recipient = subprocess.check_output([keygen, "-y", str(identity)], text=True).strip()
            ciphertext = tmp_path / "snapshot.age"
            seal(snapshot, ciphertext, recipient, binary=age)
            decoded = tmp_path / "authenticated-snapshot"
            unseal(ciphertext, decoded, identity, binary=age)
            snapshot = decoded
        assert restore_snapshot(target, snapshot, writers_stopped=True)["status"] == "restored"
        target_db.migrate()
        restored = InvestigationService(target_db, storage_for(target_db, target), target)
        assert restored.get(owner, case.id).name == "Generated restore fixture"
        assert restored.result(owner, run.id) == service.result(owner, run.id)
        assert restored.run(owner, run.id).result_checksum == checksum
        assert restored.storage.read(artifact.storage_key) == payload
        assert restored.storage.size(restored.run(owner, run.id).result_reference) > 1
        with pytest.raises(ProductError) as bounded:
            restored.result(owner, run.id, max_bytes=1)
        assert bounded.value.code == "RESULT_TRANSPORT_REQUIRED"
        with monkeypatch.context() as patch:
            patch.setattr(
                restored.storage, "read", lambda *_: pytest.fail("Full restored result read")
            )
            transport = ResultTransport(restored)
            manifest = transport.manifest(owner, run.id)
            assert manifest["chunk_count"] == 2
            assert transport.chunk(owner, run.id, 1)["result_sha256"] == checksum
        assert restored.list(Principal("different-owner")) == []
        page = restored.page(owner, search="GENERATED RESTORE")
        assert page["total"] == page["matched"] == 1
        assert [item.id for item in page["items"]] == [case.id]
        summary = page["review_summaries"][case.id]
        assert summary["run_id"] == run.id
        assert summary["candidate_count"] == len(service.result(owner, run.id)["rings"])
        assert summary["assessed"] == summary["escalated"] == 1
        assert summary["unreviewed"] == 0
        review = ReviewService(restored).get(owner, run.id, "restore-candidate")
        assert review["history"][0].note == "Generated restore review"
        assert restored.page(owner, search="%_")["matched"] == 0
        assert restored.page(Principal("different-owner"))["total"] == 0
        assert report(target_db)["status"] == "ok"
        with pytest.raises(ValueError, match="empty PostgreSQL"):
            restore_snapshot(
                target.model_copy(update={"storage_root": tmp_path / "never-written"}),
                snapshot,
                writers_stopped=True,
            )
        assert not (tmp_path / "never-written").exists()
        assert service.result(owner, run.id)["verification"] == "generated-lifecycle-fixture"
    finally:
        source_db.engine.dispose()
        target_db.engine.dispose()
