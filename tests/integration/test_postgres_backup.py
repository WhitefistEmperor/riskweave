"""Isolated real pg_dump/pg_restore drill. Never accepts a non-CI database target."""

import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform.backup import (
    create_online_database_snapshot,
    create_snapshot,
    restore_snapshot,
)
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
def test_generated_multifragment_evidence_on_real_postgres(
    databases, backend, tmp_path, monkeypatch
):
    from sqlalchemy import select

    from ringsentinel.data.ingestion import PaymentDataset, parse_input
    from ringsentinel.platform.analysis import Phase3AnalysisEngine
    from ringsentinel.platform.models import ResultSection
    from ringsentinel.platform.result_fragments import metadata, read_part
    from ringsentinel.platform.section_transport import SectionTransport
    from ringsentinel.platform.vercel_build import build
    from ringsentinel.platform.vercel_entry import MODEL_DIRECTORY

    model = build(tmp_path)
    monkeypatch.setenv(
        "RINGSENTINEL_MODEL_ARTIFACT_PATH",
        str(tmp_path / MODEL_DIRECTORY / "network-hgb.joblib"),
    )
    monkeypatch.setenv("RINGSENTINEL_MODEL_ARTIFACT_SHA256", model["sha256"])
    settings = Settings(
        environment="test",
        database_url=databases[0],
        storage_root=tmp_path / "objects",
        storage_backend=backend,
        jobs_enabled=False,
    )
    db = Database(databases[0])
    try:
        db.migrate()
        service = InvestigationService(db, storage_for(db, settings), settings)
        owner = Principal("generated-capacity-owner")
        bundle = SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=2500)).generate()
        customers = {event.customer_id for event in bundle.events}
        device = min(bundle.events, key=lambda event: (event.timestamp, event.event_id)).device_id
        suffix = "x" * 128
        dataset = PaymentDataset(
            schema_version="payments-v1",
            entities=tuple(
                entity.model_copy(update={"entity_id": entity.entity_id + suffix})
                if entity.entity_id in customers
                else entity
                for entity in bundle.entities
            ),
            events=tuple(
                event.model_copy(
                    update={
                        "customer_id": event.customer_id + suffix,
                        "device_id": device,
                    }
                )
                for event in bundle.events
            ),
        )
        content = dataset.model_dump_json().encode()
        case = service.create(owner, "Generated multi-fragment PostgreSQL control")
        artifact = service.attach(owner, case.id, content, "control.json", "application/json")
        run = service.start(owner, case.id, artifact.id, "generated-capacity")
        assert service.claim() == run.id
        service.finish(run.id, Phase3AnalysisEngine().analyze(parse_input(content)))
        saved = service.run(owner, run.id)
        fragments = metadata(service, saved)
        assert len(fragments) >= 2
        with db.session() as session:
            rows = list(
                session.scalars(
                    select(ResultSection).where(
                        ResultSection.run_id == run.id,
                        ResultSection.kind == "evidence",
                    )
                )
            )
        selected = max(rows, key=lambda row: row.size_bytes)
        assert selected.size_bytes > 2_000_000
        reads = []
        original = service.storage.read_range

        def bounded(key, offset, length):
            assert 0 < length <= 2_000_000
            value = original(key, offset, length)
            reads.append(len(value))
            return value

        monkeypatch.setattr(service.storage, "read", lambda *_: pytest.fail("Whole result read"))
        monkeypatch.setattr(service.storage, "read_range", bounded)
        digest = hashlib.sha256()
        for fragment in fragments:
            digest.update(read_part(service, saved, fragment))
        assert digest.hexdigest() == saved.result_checksum
        transport = SectionTransport(service)
        reads.clear()
        with pytest.raises(ProductError):
            transport.manifest(
                Principal("another-owner"), run.id, selected.candidate_id, "evidence"
            )
        assert reads == []
        manifest = transport.manifest(owner, run.id, selected.candidate_id, "evidence")
        assert manifest["chunk_count"] >= 2
        digest = hashlib.sha256()
        size = 0
        for index in range(manifest["chunk_count"]):
            chunk = transport.chunk(owner, run.id, selected.candidate_id, "evidence", index)
            part = base64.b64decode(chunk["data"], validate=True)
            assert hashlib.sha256(part).hexdigest() == chunk["sha256"]
            size += len(part)
            digest.update(part)
        assert size == selected.size_bytes and digest.hexdigest() == selected.checksum
        assert reads and max(reads) <= 2_000_000
    finally:
        db.engine.dispose()


def test_online_snapshot_restores_pre_export_bytes_despite_committed_erasure(
    databases, tmp_path, monkeypatch
):
    from ringsentinel.platform import backup
    from ringsentinel.platform.deletion import DeletionService

    source = Settings(
        environment="test",
        database_url=databases[0],
        storage_root=tmp_path / "source",
        storage_backend="database",
        jobs_enabled=False,
    )
    target = source.model_copy(
        update={
            "database_url": Settings(database_url=databases[1]).database_url,
            "storage_root": tmp_path / "target",
        }
    )
    source_db, target_db = Database(databases[0]), Database(databases[1])
    try:
        source_db.migrate()
        service = InvestigationService(source_db, storage_for(source_db, source), source)
        owner = Principal("online-backup-owner")
        case = service.create(owner, "Before exported snapshot")
        payload = (
            SyntheticPaymentGenerator(GenerationConfig(transactions=100))
            .generate()
            .model_dump_json()
            .encode()
        )
        artifact = service.attach(owner, case.id, payload, "input.json", "application/json")
        run = service.start(owner, case.id, artifact.id, "online-drill")
        assert service.claim() == run.id
        result = {"rings": [], "verification": "generated-lifecycle-fixture"}
        service.finish(run.id, result)
        checksum = service.run(owner, run.id).result_checksum
        command = backup.pg_command
        late_cases = []

        def write_then_dump(database, action, path, *, snapshot=None):
            assert action == "backup" and snapshot
            # Commits through another connection while the exporting transaction stays open.
            # Includes atomic removal of referenced database object bytes, not just metadata.
            DeletionService(service).remove(owner, case.id, case.name)
            assert not service.storage.exists(artifact.storage_key)
            late = service.create(owner, "After exported snapshot")
            service.attach(owner, late.id, payload, "late.json", "application/json")
            late_cases.append(late.id)
            command(database, action, path, snapshot=snapshot)

        destination = tmp_path / "snapshot"
        with monkeypatch.context() as patch:
            patch.setattr(backup, "pg_command", write_then_dump)
            manifest = create_online_database_snapshot(source, destination)
        assert manifest["consistency"] == "postgres-exported-snapshot"
        assert list(manifest["files"]) == ["database.dump"]
        assert [item.id for item in service.list(owner)] == late_cases
        assert restore_snapshot(target, destination, writers_stopped=True)["status"] == "restored"
        target_db.migrate()
        restored = InvestigationService(target_db, storage_for(target_db, target), target)
        assert [item.id for item in restored.list(owner)] == [case.id]
        assert restored.get(owner, case.id).name == case.name
        assert restored.storage.read(artifact.storage_key) == payload
        assert restored.result(owner, run.id) == result
        assert restored.run(owner, run.id).result_checksum == checksum
        assert restored.list(Principal("another-owner")) == []
    finally:
        source_db.engine.dispose()
        target_db.engine.dispose()


def test_postgres_monitor_detects_waiting_work_and_retains_records(databases, tmp_path):
    from sqlalchemy import select

    from ringsentinel.platform.models import AnalysisRun, Status, StorageDeletion, utcnow

    settings = Settings(
        environment="test",
        database_url=databases[0],
        storage_backend="database",
        storage_root=tmp_path / "objects",
        jobs_enabled=False,
        execution_mode="request",
        analysis_timeout_seconds=240,
    )
    database = Database(databases[0])
    try:
        database.migrate()
        service = InvestigationService(database, storage_for(database, settings), settings)
        owner = Principal("private-monitor-owner")
        case = service.create(owner, "Private monitor fixture")
        payload = (
            SyntheticPaymentGenerator(GenerationConfig(transactions=100))
            .generate()
            .model_dump_json()
            .encode()
        )
        artifact = service.attach(owner, case.id, payload, "private-input.json", "application/json")
        run = service.start(owner, case.id, artifact.id, "private-monitor-key")
        key = "a" * 32 + ".json"
        with database.session.begin() as session:
            saved = session.get(AnalysisRun, run.id)
            saved.created_at = utcnow() - timedelta(minutes=31)
            # The real request-mode start has a future deadline, so deadline checks miss this wait.
            assert saved.execution_deadline > utcnow()
            session.add(StorageDeletion(key=key, created_at=utcnow() - timedelta(minutes=31)))
        result = report(database)
        assert result["alerts"] == ["QUEUE_WAIT_EXCEEDED", "STORAGE_CLEANUP_OVERDUE"]
        assert result["queued_wait_exceeded"] == result["storage_cleanup_overdue"] == 1
        assert result["overdue_runs"] == 0
        assert result["oldest_queued_seconds"] >= 1860
        assert result["oldest_pending_deletion_seconds"] >= 1860
        assert report(database, queue_wait_minutes=32, cleanup_wait_minutes=32)["status"] == "ok"
        assert all(
            secret not in str(result)
            for secret in (case.id, run.id, owner.user_id, case.name, artifact.original_name, key)
        )
        with database.session() as session:
            assert session.get(AnalysisRun, run.id).status == Status.QUEUED
            assert session.get(StorageDeletion, key).attempts == 0
            assert session.scalar(select(StorageDeletion.key)) == key
    finally:
        database.engine.dispose()


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
        candidate_fixture = {
            "candidate_id": "restore-candidate",
            "risk_score": 0.8,
            "estimated_exposure_minor": 123,
            "member_entity_ids": ["generated-one", "generated-two"],
            "related_event_ids": ["generated-event"],
        }
        service.finish(
            run.id,
            {
                "rings": [{"candidate": candidate_fixture}],
                "verification": "generated-lifecycle-fixture",
                "transport_fixture": "x" * 2_000_032,
            },
        )
        from ringsentinel.platform import result_sections
        from ringsentinel.platform.models import AnalysisRun, ResultSection, ReviewDisposition

        with source_db.session.begin() as session:
            session.execute(
                delete(ResultSection).where(
                    ResultSection.run_id == run.id,
                    ResultSection.kind.in_(list(result_sections.QUEUE_FIELDS.values())),
                )
            )
            saved = session.get(AnalysisRun, run.id)
            saved.candidate_index = {
                key: value for key, value in saved.candidate_index.items() if key != "queue_present"
            }
        original_checksum = service.run(owner, run.id).result_checksum
        assert (
            result_sections.index_existing(service, writers_stopped=True, upgrade_queue=True) == 1
        )
        assert (
            result_sections.index_existing(service, writers_stopped=True, upgrade_queue=True) == 0
        )
        assert service.run(owner, run.id).result_checksum == original_checksum

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
            from ringsentinel.platform import result_sections
            from ringsentinel.platform.reviews import ReviewService

            assert (
                result_sections.value(restored, owner, run.id, "restore-candidate", "candidate")
                == candidate_fixture
            )
            assert ReviewService(restored).get(owner, run.id, "restore-candidate")["version"] == 1
            from ringsentinel.platform.section_transport import SectionTransport

            assert result_sections.page(restored, owner, run.id, limit=1)["total"] == 1
            summary = result_sections.queue_page(restored, owner, run.id, limit=1)
            assert summary["items"][0]["member_count"] == 2
            assert summary["items"][0]["event_count"] == 1
            assert "member_entity_ids" not in summary["items"][0]
            section = SectionTransport(restored)
            section_manifest = section.manifest(owner, run.id, "restore-candidate", "candidate")
            section_chunk = section.chunk(owner, run.id, "restore-candidate", "candidate", 0)
            assert section_chunk["section_sha256"] == section_manifest["sha256"]
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


def test_repeated_mixed_worker_capacity_on_linux_postgres(databases, tmp_path):
    from ringsentinel.data.ingestion import PaymentDataset
    from ringsentinel.platform.models import Status
    from ringsentinel.platform.vercel_build import build
    from ringsentinel.platform.vercel_entry import MODEL_DIRECTORY

    if sys.platform != "linux":
        pytest.skip("Linux child peak RSS measurement is configured in CI")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    model = build(tmp_path)
    settings = Settings(
        environment="test",
        database_url=databases[0],
        storage_backend="database",
        storage_root=tmp_path / "objects",
        jobs_enabled=False,
        model_artifact_path=tmp_path / MODEL_DIRECTORY / "network-hgb.joblib",
        model_artifact_sha256=model["sha256"],
        build_commit=source,
    )
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=10000)).generate()
    first = min(bundle.events, key=lambda event: (event.timestamp, event.event_id))
    other_device = next(
        event.device_id for event in bundle.events if event.device_id != first.device_id
    )
    customers = {
        customer: index
        for index, customer in enumerate(sorted({event.customer_id for event in bundle.events}))
    }
    events = tuple(
        event.model_copy(
            update={
                "device_id": first.device_id if customers[event.customer_id] % 2 else other_device,
                **({"ip_id": first.ip_id} if customers[event.customer_id] % 3 else {}),
                **({"card_id": first.card_id} if customers[event.customer_id] % 5 == 0 else {}),
            }
        )
        for event in bundle.events
    )
    content = (
        PaymentDataset(schema_version="payments-v1", entities=bundle.entities, events=events)
        .model_dump_json()
        .encode()
    )
    input_sha = hashlib.sha256(content).hexdigest()
    assert input_sha == "b6480c6ae11e14e94a25ead0a9791efedd18ab6049bbc9d76a29b270afe3c8f3"
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("RINGSENTINEL_")
    }
    environment.update(
        RINGSENTINEL_ENVIRONMENT="test",
        RINGSENTINEL_AUTH_MODE="development",
        RINGSENTINEL_JOBS_ENABLED="false",
        RINGSENTINEL_EXECUTION_MODE="local",
        RINGSENTINEL_BACKGROUND_DISPATCH="none",
        RINGSENTINEL_DATABASE_URL=databases[0],
        RINGSENTINEL_STORAGE_BACKEND="database",
        RINGSENTINEL_STORAGE_ROOT=str(settings.storage_root),
        RINGSENTINEL_MODEL_ARTIFACT_PATH=str(settings.model_artifact_path),
        RINGSENTINEL_MODEL_ARTIFACT_SHA256=model["sha256"],
        RINGSENTINEL_BUILD_COMMIT=source,
        RINGSENTINEL_ANALYSIS_TIMEOUT_SECONDS="300",
        OMP_NUM_THREADS="1",
    )
    database = Database(databases[0])
    samples = []
    try:
        database.migrate()
        with database.session() as session:
            server = session.scalar(text("SHOW server_version"))
            size_before = session.scalar(text("SELECT pg_database_size(current_database())"))
        service = InvestigationService(database, storage_for(database, settings), settings)
        owner = Principal("generated-linux-capacity-owner")
        for index in range(3):
            case = service.create(owner, "Generated Linux PostgreSQL capacity control")
            artifact = service.attach(owner, case.id, content, "control.json", "application/json")
            run = service.start(owner, case.id, artifact.id, "capacity")
            assert service.claim() == run.id
            started = time.perf_counter()
            child = subprocess.run(
                [sys.executable, "scripts/measure_linux_worker_ci.py", "--run-id", run.id],
                env=environment,
                capture_output=True,
                text=True,
                timeout=320,
            )
            wall = time.perf_counter() - started
            assert child.returncode == 0, (
                "Isolated generated worker failed; inspect private CI diagnostics"
            )
            measured = json.loads(child.stdout)
            assert measured["worker_main_seconds"] > 0 and measured["peak_worker_rss_bytes"] > 0
            assert measured["peak_rss_method"] == "proc-self-status-VmHWM"
            assert measured["worker_rss_after_bytes"] > 0
            assert measured["process_lifetime_peak_rss_bytes"] > 0
            saved = service.run(owner, run.id)
            assert saved.status == Status.COMPLETED
            assert saved.version_metadata["model_artifact_sha256"] == model["sha256"]
            assert saved.version_metadata["build_commit"] == source
            result = service.result_content(owner, run.id)
            assert hashlib.sha256(result).hexdigest() == saved.result_checksum
            with pytest.raises(ProductError):
                service.run(Principal("another-owner"), run.id)
            with database.session() as session:
                size_after = session.scalar(text("SELECT pg_database_size(current_database())"))
            samples.append(
                {
                    "repetition": index + 1,
                    "input_sha256": input_sha,
                    "result_sha256": saved.result_checksum,
                    "result_bytes": len(result),
                    "candidates": saved.candidate_count,
                    "process_wall_seconds": wall,
                    "database_size_bytes_after": size_after,
                    **measured,
                }
            )
        assert len({sample["result_sha256"] for sample in samples}) == 1
        aggregate = {
            "schema_version": "linux-postgres-worker-baseline-v1",
            "source_commit": source,
            "production_ready": False,
            "data_origin": "synthetic-control",
            "storage_backend": "database",
            "execution_mode": "local",
            "model_sha256": model["sha256"],
            "input_bytes": len(content),
            "events": len(events),
            "entities": len(bundle.entities),
            "customers": len(customers),
            "density_control": "mixed-dense-infrastructure",
            "server_version": server,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "logical_cpus": os.cpu_count(),
            "database_size_bytes_before": size_before,
            "samples": samples,
            "all_saved_results_identical": True,
            "limitations": [
                "Three sequential fresh workers on one ephemeral CI runner; "
                "not reliable percentiles, concurrency or hosted admission.",
                "Worker-main excludes module import; child wall includes startup "
                "but excludes generation/upload and parent checksum checks.",
                "VmHWM/VmRSS are approximate kernel counters for the current worker image; "
                "lifetime getrusage peak can retain pre-exec accounting. "
                "These do not measure PostgreSQL/API/parent/browser RAM. "
                "Database size is cumulative allocated disk, not RAM or storage quota usage.",
                "Local execution with PostgreSQL object storage; "
                "not hosted HTTPS/Workflow delivery or observed model accuracy.",
            ],
        }
        serialized = json.dumps(aggregate, sort_keys=True, indent=2)
        assert all(
            private not in serialized
            for private in (owner.user_id, databases[0], run.id, case.id, artifact.storage_key)
        )
        # Canonical root avoids pytest's 'current' directory alias duplicating artifacts.
        with (tmp_path.parent / "postgres-worker-capacity.json").open("x", encoding="utf-8") as out:
            out.write(serialized + "\n")
    finally:
        database.engine.dispose()
