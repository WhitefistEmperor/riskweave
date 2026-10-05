"""Read-only measurements of the synthetic Windows worker baseline's indexed results."""

import argparse
import base64
import hashlib
import json
import statistics
import subprocess
import time
from pathlib import Path

from sqlalchemy import select

from ringsentinel.platform import result_sections
from ringsentinel.platform.database import Database
from ringsentinel.platform.models import AnalysisRun, ResultSection
from ringsentinel.platform.section_transport import SectionTransport
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    baseline = json.loads((root / "report.json").read_text(encoding="utf-8"))
    if (
        baseline.get("schema_version") != "windows-worker-baseline-v1"
        or baseline.get("data_origin") != "synthetic-control"
        or baseline.get("production_ready") is not False
        or len(baseline.get("samples", [])) != 3
    ):
        raise ValueError("Requires a complete synthetic worker measurement fixture")
    destination = root / "indexed-reads.json"
    if destination.exists():
        raise ValueError("Measurement output already exists; no overwrite")
    database_url = "sqlite:///" + (root / "fixture.db").as_posix()
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=database_url,
        storage_root=root / "objects",
    )
    db = Database(database_url)
    storage = LocalStorageBackend(settings.storage_root)
    service = InvestigationService(db, storage, settings)
    owner = Principal("synthetic-capacity-only")
    transport = SectionTransport(service)
    reads = []
    original_range = storage.read_range

    def bounded_range(key, offset, length):
        if length > 2_000_000:
            raise ValueError("Unbounded indexed read")
        value = original_range(key, offset, length)
        reads.append(len(value))
        return value

    def whole_read_forbidden(*_):
        raise ValueError("Indexed measurement attempted a whole-object read")

    storage.read_range = bounded_range
    storage.read = whole_read_forbidden

    def measure(callback):
        samples = []
        for _ in range(3):
            reads.clear()
            start = time.perf_counter()
            callback()
            samples.append(
                dict(
                    seconds=time.perf_counter() - start,
                    storage_reads=len(reads),
                    storage_bytes=sum(reads),
                    largest_read_bytes=max(reads, default=0),
                )
            )
        return dict(
            repetitions=3,
            median_seconds=statistics.median(item["seconds"] for item in samples),
            samples=samples,
        )

    report = dict(
        schema_version="indexed-read-baseline-v1",
        production_ready=False,
        data_origin="synthetic-control",
        source_commit=baseline["source_commit"],
        read_source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        density_control=baseline.get("density_control", "original-generator"),
        model_sha256=baseline["model_sha256"],
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope="Local SQLite/local storage service calls; excludes HTTP, browser and hosted runtime",
        samples=[],
    )
    try:
        for original in baseline["samples"]:
            with db.session() as session:
                run = session.scalar(
                    select(AnalysisRun).where(
                        AnalysisRun.result_checksum == original["result_sha256"]
                    )
                )
                if run is None or run.version_metadata["build_commit"] != baseline["source_commit"]:
                    raise ValueError("Fixture source/result provenance mismatch")
                rows = list(
                    session.scalars(select(ResultSection).where(ResultSection.run_id == run.id))
                )
            selected = max(
                (row for row in rows if row.kind == "evidence"), key=lambda row: row.size_bytes
            )

            def verify_section(run=run, selected=selected):
                manifest = transport.manifest(owner, run.id, selected.candidate_id, "evidence")
                digest = hashlib.sha256()
                size = 0
                for index in range(manifest["chunk_count"]):
                    chunk = transport.chunk(owner, run.id, selected.candidate_id, "evidence", index)
                    content = base64.b64decode(chunk["data"], validate=True)
                    if hashlib.sha256(content).hexdigest() != chunk["sha256"]:
                        raise ValueError("Chunk digest mismatch")
                    digest.update(content)
                    size += len(content)
                if size != selected.size_bytes or digest.hexdigest() != selected.checksum:
                    raise ValueError("Section reconstruction mismatch")

            report["samples"].append(
                dict(
                    events=original["events"],
                    input_bytes=original["input_bytes"],
                    result_bytes=original["result_bytes"],
                    result_sha256=original["result_sha256"],
                    index_rows=len(rows),
                    candidates=run.candidate_count,
                    queue_indexed=bool(
                        run.candidate_index and run.candidate_index.get("queue_present")
                    ),
                    largest_candidate_bytes=max(
                        row.size_bytes for row in rows if row.kind == "candidate"
                    ),
                    largest_evidence_bytes=selected.size_bytes,
                    overview=measure(
                        lambda run=run: result_sections.overview(service, owner, run.id)
                    ),
                    first_candidate_page=measure(
                        lambda run=run: result_sections.page(
                            service, owner, run.id, offset=0, limit=8
                        )
                    ),
                    first_queue_page=measure(
                        lambda run=run: result_sections.queue_page(
                            service, owner, run.id, offset=0, limit=8
                        )
                    ),
                    selected_evidence=measure(verify_section),
                )
            )
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        db.engine.dispose()


if __name__ == "__main__":
    main()
