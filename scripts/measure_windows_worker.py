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
    parser.add_argument("--payments", type=int, nargs=3, default=(1000, 5000, 10000))
    density = parser.add_mutually_exclusive_group()
    density.add_argument(
        "--shared-device",
        action="store_true",
        help="Generated density control: every event shares one device",
    )
    density.add_argument(
        "--mixed-infrastructure",
        action="store_true",
        help="Overlapping dense device/IP/card groups",
    )
    args = parser.parse_args()
    if sys.platform != "win32":
        raise ValueError("This baseline uses Windows process counters only")
    if args.child:
        child(args.child)
        return
    if not args.directory or not args.model or not args.model_sha256:
        parser.error("directory, trusted model and SHA are required")
    if any(not 100 <= value <= 10000 for value in args.payments):
        parser.error("Each control requires 100 to 10000 requested payments")
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

    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    root = args.directory.resolve()
    database_url = "sqlite:///" + (root / "fixture.db").as_posix()
    settings = Settings(
        environment="test",
        jobs_enabled=False,
        database_url=database_url,
        storage_root=root / "objects",
        model_artifact_path=model,
        model_artifact_sha256=args.model_sha256,
        build_commit=source_commit,
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
        RINGSENTINEL_BUILD_COMMIT=source_commit,
        OMP_NUM_THREADS="1",
    )
    report = dict(
        schema_version="windows-worker-baseline-v1",
        production_ready=False,
        source_commit=source_commit,
        measurement_driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python_version=platform.python_version(),
        platform=platform.platform(),
        logical_cpus=os.cpu_count(),
        model_sha256=args.model_sha256,
        data_origin="synthetic-control",
        density_control="mixed-dense-infrastructure"
        if args.mixed_infrastructure
        else "all-events-share-one-device"
        if args.shared_device
        else "original-generator",
        samples=[],
    )
    try:
        for requested in args.payments:
            bundle = SyntheticPaymentGenerator(
                GenerationConfig(seed=105, transactions=requested)
            ).generate()
            shared_device = min(
                bundle.events, key=lambda item: (item.timestamp, item.event_id)
            ).device_id
            events = bundle.events
            if args.shared_device:
                events = tuple(
                    event.model_copy(update={"device_id": shared_device}) for event in events
                )
            elif args.mixed_infrastructure:
                first = min(events, key=lambda event: (event.timestamp, event.event_id))
                other_device = next(
                    event.device_id for event in events if event.device_id != shared_device
                )
                customer_order = {
                    customer: index
                    for index, customer in enumerate(
                        sorted({event.customer_id for event in events})
                    )
                }
                events = tuple(
                    event.model_copy(
                        update={
                            "device_id": shared_device
                            if customer_order[event.customer_id] % 2
                            else other_device,
                            **(
                                {"ip_id": first.ip_id}
                                if customer_order[event.customer_id] % 3
                                else {}
                            ),
                            **(
                                {"card_id": first.card_id}
                                if customer_order[event.customer_id] % 5 == 0
                                else {}
                            ),
                        }
                    )
                    for event in events
                )
            payments = PaymentDataset(
                schema_version="payments-v1",
                entities=bundle.entities,
                events=events,
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
            assert saved.version_metadata["model_artifact_sha256"] == args.model_sha256
            assert saved.version_metadata["build_commit"] == source_commit
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
                distinct_customers=len({event.customer_id for event in payments.events}),
                distinct_devices=len({event.device_id for event in payments.events}),
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
