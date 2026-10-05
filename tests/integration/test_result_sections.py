"""Verified targeted reads over large generated results in both object stores."""

import hashlib

import pytest
from sqlalchemy import delete, func, select

from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
from ringsentinel.platform import result_sections
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import AnalysisRun, ResultSection, ReviewDisposition
from ringsentinel.platform.reviews import ReviewService
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings


@pytest.fixture(params=["local", "database"])
def saved(tmp_path, request):
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=f"sqlite:///{tmp_path / 'sections.db'}",
        storage_root=tmp_path / "objects",
        storage_backend=request.param,
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    service = InvestigationService(db, storage_for(db, settings), settings)
    owner = Principal("sections-owner")
    case = service.create(owner, "Generated targeted-read control")
    payload = (
        SyntheticPaymentGenerator(GenerationConfig(transactions=100))
        .generate()
        .model_dump_json()
        .encode()
    )
    artifact = service.attach(owner, case.id, payload, "input.json", "application/json")
    run = service.start(owner, case.id, artifact.id, "sections-control")
    service.claim()
    result = {
        "currency": "INR",
        "earlier": {"rings": ["nested decoy"]},
        "padding": "x" * 3_000_001,
        "rings": [
            {
                "candidate": {"candidate_id": "first", "name": "Unicode € 测试"},
                "queries": {"sample": {"text": "Unicode € evidence"}},
            },
            {
                "candidate": {"candidate_id": "second"},
                "queries": {"sample": {"number": 2, "text": "z" * 2_100_001}},
            },
        ],
    }
    service.finish(run.id, result)
    yield service, owner, case, run.id, result
    db.engine.dispose()


def test_large_result_targeted_reads_reviews_and_erasure_without_full_read(saved, monkeypatch):
    service, owner, case, run_id, result = saved
    original = service.run(owner, run_id).result_checksum
    monkeypatch.setattr(service.storage, "read", lambda *_: pytest.fail("Full result read"))
    assert result_sections.candidates(service, owner, run_id) == [
        r["candidate"] for r in result["rings"]
    ]
    assert (
        result_sections.value(service, owner, run_id, "first", "candidate")
        == result["rings"][0]["candidate"]
    )
    assert (
        result_sections.value(service, owner, run_id, "second", "evidence")
        == result["rings"][1]["queries"]
    )
    assert result_sections.currency(service, owner, run_id) == "INR"
    reviews = ReviewService(service)
    assert reviews.get(owner, run_id, "first")["version"] == 0
    assert (
        reviews.save(owner, run_id, "first", ReviewDisposition.ESCALATED, "Generated", 0, "review")[
            "version"
        ]
        == 1
    )
    for kind in ("candidate", "evidence"):
        with pytest.raises(ProductError) as denied:
            result_sections.value(service, Principal("other-owner"), run_id, "first", kind)
        assert denied.value.code == "NOT_FOUND"
    with pytest.raises(ProductError) as missing:
        reviews.get(owner, run_id, "absent")
    assert missing.value.code == "NOT_FOUND"
    assert service.run(owner, run_id).result_checksum == original
    assert DeletionService(service).remove(owner, case.id, case.name)["status"] == "deleted"
    with service.database.session() as session:
        assert session.scalar(select(func.count()).select_from(ResultSection)) == 0


def test_missing_or_corrupt_index_fails_closed(saved):
    service, owner, _, run_id, _ = saved
    with service.database.session.begin() as session:
        session.get(ResultSection, (run_id, "evidence", "first")).checksum = "0" * 64
    with pytest.raises(ProductError) as corrupt:
        result_sections.value(service, owner, run_id, "first", "evidence")
    assert corrupt.value.code == "INTERNAL_ERROR"
    with service.database.session.begin() as session:
        session.execute(
            delete(ResultSection).where(
                ResultSection.run_id == run_id,
                ResultSection.kind == "candidate",
                ResultSection.candidate_id == "first",
            )
        )
    with pytest.raises(ProductError) as missing:
        ReviewService(service).get(owner, run_id, "second")
    assert missing.value.code == "INTERNAL_ERROR"


def test_legacy_fallback_and_explicit_idempotent_indexing_preserve_bytes(saved, monkeypatch):
    service, owner, _, run_id, result = saved
    checksum = service.run(owner, run_id).result_checksum
    with service.database.session.begin() as session:
        session.execute(delete(ResultSection).where(ResultSection.run_id == run_id))
        run = session.get(AnalysisRun, run_id)
        run.candidate_index = None
        run.candidate_count = None
    assert (
        result_sections.value(service, owner, run_id, "first", "evidence")
        == result["rings"][0]["queries"]
    )
    with pytest.raises(ValueError):
        result_sections.index_existing(service)
    assert result_sections.index_existing(service, writers_stopped=True) == 1
    assert result_sections.index_existing(service, writers_stopped=True) == 0
    assert service.run(owner, run_id).result_checksum == checksum
    assert hashlib.sha256(service.result_content(owner, run_id)).hexdigest() == checksum
    monkeypatch.setattr(
        service.storage, "read", lambda *_: pytest.fail("Full read after maintenance")
    )
    assert (
        result_sections.value(service, owner, run_id, "second", "candidate")["candidate_id"]
        == "second"
    )


def test_section_index_failure_rolls_back_result_and_rows(saved, monkeypatch):
    service, owner, case, _, _ = saved
    artifact = service.artifacts(owner, case.id)[0]
    run = service.start(owner, case.id, artifact.id, "failed-index")
    service.claim()
    original_save = service._save
    keys = []

    def save(session, content):
        obj = original_save(session, content)
        keys.append(obj.key)
        return obj

    def failed(*_):
        raise ValueError("Generated section indexing failure")

    monkeypatch.setattr(service, "_save", save)
    monkeypatch.setattr(result_sections, "index_in", failed)
    with pytest.raises(ValueError):
        service.finish(run.id, {"rings": [{"candidate": {"candidate_id": "failed"}}]})
    assert service.run(owner, run.id).result_reference is None
    assert service.run(owner, run.id).candidate_index is None
    assert all(not service.storage.exists(key) for key in keys)
    with service.database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ResultSection)
                .where(ResultSection.run_id == run.id)
            )
            == 0
        )


def test_targeted_large_evidence_uses_bounded_ranges_and_rejects_byte_corruption(
    saved, monkeypatch
):
    service, owner, _, run_id, result = saved
    original_read = service.storage.read_range
    lengths = []

    def ranged(key, offset, length):
        lengths.append(length)
        assert 0 < length <= 2_000_000
        return original_read(key, offset, length)

    monkeypatch.setattr(service.storage, "read", lambda *_: pytest.fail("Whole object read"))
    monkeypatch.setattr(service.storage, "read_range", ranged)
    assert (
        result_sections.value(service, owner, run_id, "second", "evidence")
        == result["rings"][1]["queries"]
    )
    assert 2_000_000 in lengths

    def corrupt(key, offset, length):
        part = bytearray(original_read(key, offset, length))
        part[-1] ^= 1
        return bytes(part)

    monkeypatch.setattr(service.storage, "read_range", corrupt)
    with pytest.raises(ProductError) as failure:
        result_sections.value(service, owner, run_id, "second", "evidence")
    assert failure.value.code == "INTERNAL_ERROR"


def test_legacy_indexing_refuses_active_analysis_without_mutating_marker(saved):
    service, owner, case, run_id, _ = saved
    with service.database.session.begin() as session:
        session.execute(delete(ResultSection).where(ResultSection.run_id == run_id))
        session.get(AnalysisRun, run_id).candidate_index = None
    artifact = service.artifacts(owner, case.id)[0]
    service.start(owner, case.id, artifact.id, "active-blocks-maintenance")
    with pytest.raises(ValueError, match="Active analysis"):
        result_sections.index_existing(service, writers_stopped=True)
    assert service.run(owner, run_id).candidate_index is None
