"""Owner-scoped verified ranges over unchanged canonical result bytes."""

import hashlib
import json
import re

from sqlalchemy import func, select

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import ResultSection, Status


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


OVERVIEW_FIELDS = ("schema_version", "threshold", "event_count", "entity_count", "model_scope")


def index_in(session, run, result, content):
    if run.candidate_count is None:
        return
    rows = []

    def section(kind, candidate_id, ordinal, offset, value):
        encoded = encode(value)
        if memoryview(content)[offset : offset + len(encoded)] != encoded:
            raise ValueError("Canonical section mismatch")
        rows.append(
            ResultSection(
                run_id=run.id,
                kind=kind,
                candidate_id=candidate_id,
                ordinal=ordinal,
                byte_offset=offset,
                size_bytes=len(encoded),
                checksum=hashlib.sha256(encoded).hexdigest(),
            )
        )

    offset = 1
    for position, key in enumerate(sorted(result)):
        offset += (1 if position else 0) + len(encode(key)) + 1
        value = result[key]
        if key in (*OVERVIEW_FIELDS, "currency"):
            section(key, "", 0, offset, value)
        if key == "rings":
            offset += 1
            for ordinal, ring in enumerate(value):
                offset += 1 if ordinal else 0
                candidate_id = ring["candidate"]["candidate_id"]
                nested = offset + 1
                for number, name in enumerate(sorted(ring)):
                    nested += (1 if number else 0) + len(encode(name)) + 1
                    if name in ("candidate", "queries"):
                        section(
                            "candidate" if name == "candidate" else "evidence",
                            candidate_id,
                            ordinal,
                            nested,
                            ring[name],
                        )
                    nested += len(encode(ring[name]))
                offset = nested + 1
            offset += 1
        else:
            offset += len(encode(value))
    if offset + 1 != len(content):
        raise ValueError("Canonical result length mismatch")
    session.add_all(rows)
    run.candidate_index = {
        "version": 1,
        "count": run.candidate_count,
        "currency_present": "currency" in result,
        "overview_present": all(key in result for key in OVERVIEW_FIELDS),
    }


def authorized(service, principal, run_id):
    run = service.run(principal, run_id)
    if run.status != Status.COMPLETED or not run.result_reference:
        raise ProductError("CONFLICT")
    if run.candidate_index is not None:
        marker = run.candidate_index
        if (
            not isinstance(marker, dict)
            or set(marker)
            not in (
                {"version", "count", "currency_present"},
                {"version", "count", "currency_present", "overview_present"},
            )
            or ("overview_present" in marker and type(marker["overview_present"]) is not bool)
            or type(marker["version"]) is not int
            or marker["version"] != 1
            or type(marker["count"]) is not int
            or marker["count"] != run.candidate_count
            or marker["count"] < 0
            or type(marker["currency_present"]) is not bool
        ):
            raise ProductError("INTERNAL_ERROR")
        with service.database.session() as session:
            count = session.scalar(
                select(func.count())
                .select_from(ResultSection)
                .where(ResultSection.run_id == run.id, ResultSection.kind == "candidate")
            )
        if count != marker["count"]:
            raise ProductError("INTERNAL_ERROR")
    return run


def read(service, run, row):
    if (
        type(row.byte_offset) is not int
        or row.byte_offset < 0
        or type(row.size_bytes) is not int
        or row.size_bytes <= 0
        or run.result_size_bytes is None
        or row.byte_offset + row.size_bytes > run.result_size_bytes
        or not re.fullmatch(r"[a-f0-9]{64}", row.checksum)
        or service.storage.size(run.result_reference) != run.result_size_bytes
    ):
        raise ProductError("INTERNAL_ERROR")
    content = bytearray()
    digest = hashlib.sha256()
    for offset in range(0, row.size_bytes, 2_000_000):
        length = min(2_000_000, row.size_bytes - offset)
        part = service.storage.read_range(run.result_reference, row.byte_offset + offset, length)
        if len(part) != length:
            raise ProductError("INTERNAL_ERROR")
        digest.update(part)
        content.extend(part)
    if digest.hexdigest() != row.checksum:
        raise ProductError("INTERNAL_ERROR")
    return json.loads(content)


def row_for(service, run, kind, candidate_id):
    with service.database.session() as session:
        return session.get(ResultSection, (run.id, kind, candidate_id))


def require_candidate(service, principal, run_id, candidate_id):
    run = authorized(service, principal, run_id)
    if run.candidate_index is None:
        if not any(
            ring["candidate"]["candidate_id"] == candidate_id
            for ring in service.result(principal, run_id)["rings"]
        ):
            raise ProductError("NOT_FOUND")
    else:
        row = row_for(service, run, "candidate", candidate_id)
        if row is None:
            raise ProductError("NOT_FOUND")
        if read(service, run, row).get("candidate_id") != candidate_id:
            raise ProductError("INTERNAL_ERROR")
    return run


def value(service, principal, run_id, candidate_id, kind):
    run = require_candidate(service, principal, run_id, candidate_id)
    if run.candidate_index is None:
        ring = next(
            r
            for r in service.result(principal, run_id)["rings"]
            if r["candidate"]["candidate_id"] == candidate_id
        )
        return ring["candidate" if kind == "candidate" else "queries"]
    row = row_for(service, run, kind, candidate_id)
    if row is None:
        raise ProductError("INTERNAL_ERROR")
    result = read(service, run, row)
    if kind == "candidate" and result.get("candidate_id") != candidate_id:
        raise ProductError("INTERNAL_ERROR")
    return result


def candidates(service, principal, run_id):
    run = authorized(service, principal, run_id)
    if run.candidate_index is None:
        return [ring["candidate"] for ring in service.result(principal, run_id)["rings"]]
    with service.database.session() as session:
        rows = list(
            session.scalars(
                select(ResultSection)
                .where(ResultSection.run_id == run.id, ResultSection.kind == "candidate")
                .order_by(ResultSection.ordinal)
            )
        )
    result = []
    for ordinal, row in enumerate(rows):
        candidate = read(service, run, row)
        if row.ordinal != ordinal or candidate.get("candidate_id") != row.candidate_id:
            raise ProductError("INTERNAL_ERROR")
        result.append(candidate)
    return result


def currency(service, principal, run_id):
    run = authorized(service, principal, run_id)
    if run.candidate_index is None:
        return service.result(principal, run_id).get("currency")
    if not run.candidate_index["currency_present"]:
        return None
    row = row_for(service, run, "currency", "")
    if row is None:
        raise ProductError("INTERNAL_ERROR")
    return read(service, run, row)


def index_existing(service, *, writers_stopped=False, limit=100):
    from ringsentinel.platform.models import AnalysisRun
    from ringsentinel.platform.result_fragments import existing_database
    from ringsentinel.platform.worklist_reviews import candidate_count

    if not writers_stopped or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Stop all writers and choose a bounded batch")
    existing_database(service.database)
    indexed, cursor = 0, ""
    for _ in range(limit):
        with service._write() as session:
            if session.scalar(
                select(AnalysisRun.id)
                .where(AnalysisRun.status.in_([Status.QUEUED, Status.RUNNING]))
                .limit(1)
            ):
                raise ValueError("Active analysis prevents indexing")
            run = session.scalar(
                select(AnalysisRun)
                .where(
                    AnalysisRun.status == Status.COMPLETED,
                    AnalysisRun.id > cursor,
                    AnalysisRun.candidate_index.is_(None),
                )
                .order_by(AnalysisRun.id)
                .limit(1)
            )
            if run is None:
                break
            cursor = run.id
            if session.scalar(
                select(ResultSection.run_id).where(ResultSection.run_id == run.id).limit(1)
            ):
                raise ProductError("INTERNAL_ERROR")
            content = service.storage.read(run.result_reference)
            if (
                not 0 < len(content) <= 500_000_000
                or hashlib.sha256(content).hexdigest() != run.result_checksum
            ):
                raise ProductError("INTERNAL_ERROR")
            result = json.loads(content)
            count = candidate_count(result)
            if count is None:
                continue
            run.candidate_count = count
            if run.result_size_bytes is None:
                from ringsentinel.platform.result_fragments import index_in as index_fragments

                index_fragments(session, run, content)
            elif run.result_size_bytes != len(content):
                raise ProductError("INTERNAL_ERROR")
            index_in(session, run, result, content)
            indexed += 1
    return indexed


def main():
    import argparse

    from ringsentinel.platform.database import Database
    from ringsentinel.platform.database_storage import storage_for
    from ringsentinel.platform.service import InvestigationService
    from ringsentinel.platform.settings import Settings

    parser = argparse.ArgumentParser(
        description="Index legacy candidate sections with stopped writers"
    )
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    database = None
    try:
        if not args.writers_stopped:
            raise ValueError("Stop writers first")
        settings = Settings()
        database = Database(settings.database_url.get_secret_value())
        service = InvestigationService(database, storage_for(database, settings), settings)
        count = index_existing(service, writers_stopped=True, limit=args.limit)
        print(json.dumps({"status": "indexed", "count": count}))
    except Exception:
        print(json.dumps({"status": "unavailable", "code": "RESULT_SECTION_INDEX_UNAVAILABLE"}))
        raise SystemExit(2) from None
    finally:
        if database:
            database.engine.dispose()


if __name__ == "__main__":
    main()


def page(service, principal, run_id, *, offset=0, limit=50):
    run = authorized(service, principal, run_id)
    if (
        type(offset) is not int
        or not 0 <= offset <= 500_000_000
        or type(limit) is not int
        or not 1 <= limit <= 100
    ):
        raise ValueError("Invalid candidate page")
    if run.candidate_index is None:
        entries = [ring["candidate"] for ring in service.result(principal, run_id)["rings"]]
        total, items = len(entries), entries[offset : offset + limit]
    else:
        total = run.candidate_index["count"]
        with service.database.session() as session:
            rows = list(
                session.scalars(
                    select(ResultSection)
                    .where(
                        ResultSection.run_id == run.id,
                        ResultSection.kind == "candidate",
                        ResultSection.ordinal >= offset,
                        ResultSection.ordinal < offset + limit,
                    )
                    .order_by(ResultSection.ordinal)
                )
            )
        if len(rows) != min(limit, max(total - offset, 0)):
            raise ProductError("INTERNAL_ERROR")
        items = []
        for ordinal, row in enumerate(rows, start=offset):
            candidate = read(service, run, row)
            if row.ordinal != ordinal or candidate.get("candidate_id") != row.candidate_id:
                raise ProductError("INTERNAL_ERROR")
            items.append(candidate)
    return {
        "schema_version": "1",
        "run_id": run.id,
        "result_sha256": run.result_checksum,
        "offset": offset,
        "limit": limit,
        "total": total,
        "items": items,
        "next_offset": offset + len(items) if offset + len(items) < total else None,
    }


def overview(service, principal, run_id):
    run = authorized(service, principal, run_id)
    if run.candidate_index and run.candidate_index.get("overview_present"):
        values = {}
        for key in OVERVIEW_FIELDS:
            row = row_for(service, run, key, "")
            if row is None:
                raise ProductError("INTERNAL_ERROR")
            values[key] = read(service, run, row)
        values["currency"] = currency(service, principal, run_id)
        total = run.candidate_count
    else:
        result = service.result(principal, run_id)
        values = {key: result[key] for key in OVERVIEW_FIELDS}
        values["currency"] = result.get("currency")
        total = len(result["rings"])
    return {
        **values,
        "run_id": run.id,
        "result_sha256": run.result_checksum,
        "candidate_count": total,
    }
