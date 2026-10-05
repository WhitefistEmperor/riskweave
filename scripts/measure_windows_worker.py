"""Windows-only synthetic worker baseline; creates only a new private fixture directory."""

import argparse
import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path


def peak_memory():
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    query.restype = wintypes.BOOL
    if not query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise OSError("Memory observation failed")
    return dict(
        peak_working_set_bytes=counters.PeakWorkingSetSize,
        peak_commit_bytes=counters.PeakPagefileUsage,
    )


def child(run_id):
    from ringsentinel.platform.worker import main

    sys.argv = ["worker", run_id]
    start = time.perf_counter()
    main()
    print(json.dumps(dict(worker_main_seconds=time.perf_counter() - start, **peak_memory())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child")
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--model-sha256")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise ValueError("This baseline uses Windows process counters only")
    if args.child:
        child(args.child)
        return
    if not args.directory or not args.model or not args.model_sha256:
        parser.error("directory, trusted model and SHA are required")
    # Check the trust pin without deserializing; operator must trust the model source.
    model = args.model.resolve()
    if hashlib.sha256(model.read_bytes()).hexdigest() != args.model_sha256:
        raise ValueError("Model pin mismatch")
    args.directory.mkdir()  # No existing directory, cases or outputs are overwritten.
    from ringsentinel import GenerationConfig, SyntheticPaymentGenerator
    from ringsentinel.data.ingestion import PaymentDataset
    from ringsentinel.platform.database import Database
    from ringsentinel.platform.service import InvestigationService, Principal
    from ringsentinel.platform.settings import Settings
    from ringsentinel.platform.storage import LocalStorageBackend

    root = args.directory.resolve()
    database_url = "sqlite:///" + (root / "fixture.db").as_posix()
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=database_url,
        storage_root=root / "objects",
    )
    database = Database(database_url)
    database.migrate()
    service = InvestigationService(database, LocalStorageBackend(settings.storage_root), settings)
    owner = Principal("synthetic-capacity-only")
    env = {key: value for key, value in os.environ.items() if not key.startswith("RINGSENTINEL_")}
    env.update(
        RINGSENTINEL_ENVIRONMENT="test",
        RINGSENTINEL_AUTH_MODE="development",
        RINGSENTINEL_JOBS_ENABLED="false",
        RINGSENTINEL_DATABASE_URL=database_url,
        RINGSENTINEL_STORAGE_ROOT=str(settings.storage_root),
        RINGSENTINEL_STORAGE_BACKEND="local",
        RINGSENTINEL_EXECUTION_MODE="local",
        RINGSENTINEL_MODEL_ARTIFACT_PATH=str(model),
        RINGSENTINEL_MODEL_ARTIFACT_SHA256=args.model_sha256,
        RINGSENTINEL_ANALYSIS_TIMEOUT_SECONDS="300",
        OMP_NUM_THREADS="1",
    )
    report = dict(
        schema_version="windows-worker-baseline-v1",
        production_ready=False,
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        python_version=platform.python_version(),
        platform=platform.platform(),
        logical_cpus=os.cpu_count(),
        model_sha256=args.model_sha256,
        data_origin="synthetic-control",
        samples=[],
    )
    try:
        for requested in (1000, 5000, 10000):
            bundle = SyntheticPaymentGenerator(
                GenerationConfig(seed=105, transactions=requested)
            ).generate()
            payments = PaymentDataset(
                schema_version="payments-v1", entities=bundle.entities, events=bundle.events
            )
            content = payments.model_dump_json().encode()
            case = service.create(owner, "Synthetic capacity fixture")
            artifact = service.attach(owner, case.id, content, "control.json", "application/json")
            run = service.start(owner, case.id, artifact.id, "capacity")
            assert service.claim() == run.id
            start = time.perf_counter()
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--child", run.id],
                env=env,
                capture_output=True,
                text=True,
                timeout=320,
            )
            if process.returncode:
                raise RuntimeError("Synthetic worker failed; inspect private fixture locally")
            measured = json.loads(process.stdout)
            saved = service.run(owner, run.id)
            assert saved.status.value == "completed"
            result = service.result_content(owner, run.id)
            assert hashlib.sha256(result).hexdigest() == saved.result_checksum
            sample = dict(
                requested_payments=requested,
                events=len(payments.events),
                entities=len(payments.entities),
                input_bytes=len(content),
                result_bytes=len(result),
                input_sha256=hashlib.sha256(content).hexdigest(),
                result_sha256=saved.result_checksum,
                candidates=saved.candidate_count,
                process_wall_seconds=time.perf_counter() - start,
                **measured,
            )
            report["samples"].append(sample)
            (root / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(sample), flush=True)
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
