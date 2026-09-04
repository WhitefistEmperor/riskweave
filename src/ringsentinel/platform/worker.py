"""Isolated analysis process. Never launched with user-supplied shell commands."""

import hashlib
import sys

from ringsentinel.data.schema import DatasetBundle
from ringsentinel.platform.analysis import Phase3AnalysisEngine
from ringsentinel.platform.database import Database
from ringsentinel.platform.models import AnalysisRun, Artifact, Status
from ringsentinel.platform.service import InvestigationService
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import LocalStorageBackend


def main():
    settings = Settings()
    database = Database(settings.database_url.get_secret_value())
    storage = LocalStorageBackend(settings.storage_root)
    service = InvestigationService(database, storage, settings)
    run_id = sys.argv[1]
    try:
        with database.session() as session:
            run = session.get(AnalysisRun, run_id)
            if run is None or run.status != Status.RUNNING:
                raise ValueError("Run is not claimed")
            artifact = session.get(Artifact, run.artifact_id)
            content = storage.read(artifact.storage_key)
            if hashlib.sha256(content).hexdigest() != artifact.checksum:
                raise ValueError("Input checksum mismatch")
        result = Phase3AnalysisEngine().analyze(DatasetBundle.model_validate_json(content))
        service.finish(run_id, result)
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
