"""Single scheduler, database-backed queue, one killable subprocess per analysis.

Not a distributed job system. Run exactly one API worker with this executor.
Crash recovery marks running work failed; queued work remains eligible.
"""

import json
import logging
import os
import subprocess
import sys
import time
from threading import Event, Thread
from typing import Protocol

from ringsentinel.platform.locking import ExecutorLease, FileLock
from ringsentinel.platform.service import InvestigationService

logger = logging.getLogger("ringsentinel.jobs")


class JobExecutor(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class LocalJobExecutor:
    def __init__(self, service: InvestigationService):
        self.service = service
        self.stopping = Event()
        self.thread: Thread | None = None
        self.lease = ExecutorLease(service.database, service.settings.storage_root)
        self.owns_lease = False

    def start(self):
        if self.thread is not None:
            raise RuntimeError("Executor already started")
        self.lease.acquire()
        self.owns_lease = True
        try:
            with FileLock(self.service.settings.storage_root / ".analysis.lock"):
                self.service.recover_interrupted()
            self.thread = Thread(target=self._loop, name="analysis-scheduler", daemon=True)
            self.thread.start()
        except Exception:
            self.lease.release()
            self.owns_lease = False
            raise

    def stop(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError("Executor did not stop; ownership retained")
        if self.owns_lease:
            self.lease.release()
            self.owns_lease = False

    def _loop(self):
        while not self.stopping.wait(0.25):
            try:
                self.lease.check()
            except Exception:
                logger.error(json.dumps({"event": "executor_lease_lost"}))
                self.stopping.set()
                return
            try:
                run_id = self.service.claim()
                if run_id:
                    self.execute(run_id)
            except Exception:
                # Deliberately exclude exception strings (DB URLs/input data may be embedded).
                logger.error(json.dumps({"event": "worker_error", "failure_category": "internal"}))

    def execute(self, run_id: str):
        started = time.monotonic()
        settings = self.service.settings
        environment = dict(os.environ)
        environment["RINGSENTINEL_DATABASE_URL"] = settings.database_url.get_secret_value()
        environment["RINGSENTINEL_STORAGE_ROOT"] = str(settings.storage_root.resolve())
        environment["RINGSENTINEL_ENVIRONMENT"] = "test"
        environment["RINGSENTINEL_AUTH_MODE"] = "disabled"
        environment["RINGSENTINEL_STORAGE_LIMIT_BYTES"] = str(settings.storage_limit_bytes)
        environment["RINGSENTINEL_RESULT_LIMIT_BYTES"] = str(settings.result_limit_bytes)
        environment["RINGSENTINEL_ANALYSIS_TIMEOUT_SECONDS"] = str(
            settings.analysis_timeout_seconds
        )
        # Analysis never needs a provider or signing/auth credentials.
        environment.pop("OPENAI_API_KEY", None)
        environment["RINGSENTINEL_LLM_PROVIDER"] = "disabled"
        error_code = None
        process = None
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "ringsentinel.platform.worker", run_id],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + settings.analysis_timeout_seconds
            while process.poll() is None:
                if self.owns_lease:
                    self.lease.check()
                if self.stopping.wait(0.1):
                    error_code = "WORKER_INTERRUPTED"
                    break
                if time.monotonic() >= deadline:
                    error_code = "ANALYSIS_TIMEOUT"
                    break
            if error_code:
                process.kill()
                process.wait(timeout=5)
            elif process.returncode:
                error_code = "ANALYSIS_FAILED"
        except Exception:
            error_code = "ANALYSIS_FAILED"
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        if error_code:
            from ringsentinel.platform.models import AnalysisRun, Status

            with self.service.database.session() as session:
                run = session.get(AnalysisRun, run_id)
                unfinished = run is not None and run.status == Status.RUNNING
            if unfinished:
                self.service.finish(run_id, error_code=error_code)
        from ringsentinel.platform.models import AnalysisRun

        with self.service.database.session() as session:
            record = session.get(AnalysisRun, run_id)
            status = record.status.value if record else "missing"
        logger.info(
            json.dumps(
                {
                    "event": "analysis_finished",
                    "run_id": run_id,
                    "failure_category": error_code,
                    "status": status,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                }
            )
        )
