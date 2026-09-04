"""Single scheduler, database-backed queue, one killable subprocess per analysis.

Not a distributed job system. Run exactly one API worker with this executor.
Crash recovery marks running work failed; queued work remains eligible.
"""

import json
import logging
import os
import subprocess
import sys
from threading import Event, Thread
from typing import Protocol

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

    def start(self):
        self.service.recover_interrupted()
        self.thread = Thread(target=self._loop, name="analysis-scheduler", daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=10)

    def _loop(self):
        while not self.stopping.wait(0.25):
            try:
                run_id = self.service.claim()
                if run_id:
                    self.execute(run_id)
            except Exception:
                # Deliberately exclude exception strings (DB URLs/input data may be embedded).
                logger.error(json.dumps({"event": "worker_error", "failure_category": "internal"}))

    def execute(self, run_id: str):
        settings = self.service.settings
        environment = dict(os.environ)
        environment["RINGSENTINEL_DATABASE_URL"] = settings.database_url.get_secret_value()
        environment["RINGSENTINEL_STORAGE_ROOT"] = str(settings.storage_root.resolve())
        environment["RINGSENTINEL_ENVIRONMENT"] = "test"
        error_code = None
        process = None
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "ringsentinel.platform.worker", run_id],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            import time

            deadline = time.monotonic() + settings.analysis_timeout_seconds
            while process.poll() is None:
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
        logger.info(
            json.dumps(
                {"event": "analysis_finished", "run_id": run_id, "failure_category": error_code}
            )
        )
