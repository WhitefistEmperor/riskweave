"""Owner-scoped transactional application service, independent of HTTP and execution."""

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from ringsentinel import __version__
from ringsentinel.data.schema import DatasetBundle
from ringsentinel.data.validation import validate_dataset
from ringsentinel.platform.database import Database
from ringsentinel.platform.errors import ERRORS, ProductError
from ringsentinel.platform.models import AnalysisRun, Artifact, Investigation, Status, User, utcnow
from ringsentinel.platform.settings import Settings
from ringsentinel.platform.storage import StorageBackend


@dataclass(frozen=True)
class Principal:
    user_id: str


class InvestigationService:
    def __init__(self, database: Database, storage: StorageBackend, settings: Settings):
        self.database, self.storage, self.settings = database, storage, settings

    @contextmanager
    def _write(self):
        with self.database.session.begin() as session:
            if self.database.engine.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            else:
                session.execute(text("SELECT pg_advisory_xact_lock(593002)"))
            yield session

    @staticmethod
    def _quota(session, model, limit, *conditions):
        if session.scalar(select(func.count()).select_from(model).where(*conditions)) >= limit:
            raise ProductError("QUOTA_EXCEEDED")

    def _owned(self, session, principal: Principal, investigation_id: str):
        item = session.scalar(
            select(Investigation).where(
                Investigation.id == investigation_id, Investigation.owner_id == principal.user_id
            )
        )
        if item is None:
            raise ProductError("NOT_FOUND")
        return item

    def create(self, principal: Principal, name: str) -> Investigation:
        with self._write() as session:
            self._quota(session, Investigation, self.settings.max_investigations_total)
            self._quota(
                session,
                Investigation,
                self.settings.max_investigations_per_owner,
                Investigation.owner_id == principal.user_id,
            )
            if session.get(User, principal.user_id) is None:
                session.add(User(id=principal.user_id))
                session.flush()
            item = Investigation(owner_id=principal.user_id, name=name, status=Status.CREATED)
            session.add(item)
        return item

    def list(self, principal: Principal) -> list[Investigation]:
        with self.database.session() as session:
            return list(
                session.scalars(
                    select(Investigation)
                    .where(Investigation.owner_id == principal.user_id)
                    .order_by(Investigation.created_at, Investigation.id)
                )
            )

    def get(self, principal: Principal, investigation_id: str) -> Investigation:
        with self.database.session() as session:
            return self._owned(session, principal, investigation_id)

    def artifacts(self, principal: Principal, investigation_id: str) -> list[Artifact]:
        with self.database.session() as session:
            self._owned(session, principal, investigation_id)
            return list(
                session.scalars(
                    select(Artifact)
                    .where(Artifact.investigation_id == investigation_id)
                    .order_by(Artifact.created_at, Artifact.id)
                )
            )

    def attach(
        self,
        principal: Principal,
        investigation_id: str,
        content: bytes,
        name: str,
        content_type: str,
    ) -> Artifact:
        self.get(principal, investigation_id)
        if len(content) > self.settings.upload_limit_bytes:
            raise ProductError("UPLOAD_TOO_LARGE")
        if content_type.split(";")[0] != "application/json":
            raise ProductError("INVALID_DATASET")
        try:
            bundle = DatasetBundle.model_validate_json(content)
            validate_dataset(bundle)
            if not bundle.events:
                raise ValueError("Empty dataset")
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProductError("INVALID_DATASET") from None
        checksum = hashlib.sha256(content).hexdigest()
        saved = None
        try:
            with self._write() as session:
                item = self._owned(session, principal, investigation_id)
                previous_status = item.status
                self._lock_idle(session, item.id, Status.UPLOADING)
                existing = session.scalar(
                    select(Artifact).where(
                        Artifact.investigation_id == item.id, Artifact.checksum == checksum
                    )
                )
                if existing:
                    session.execute(
                        update(Investigation)
                        .where(Investigation.id == item.id)
                        .values(status=previous_status)
                    )
                    return existing
                self._quota(
                    session,
                    Artifact,
                    self.settings.max_artifacts_per_investigation,
                    Artifact.investigation_id == item.id,
                )
                saved = self.storage.save(content)
                safe_name = PurePosixPath(name.replace("\\", "/")).name
                safe_name = "".join(c for c in safe_name if c.isprintable())[:200] or "dataset.json"
                artifact = Artifact(
                    investigation_id=item.id,
                    original_name=safe_name,
                    storage_key=saved.key,
                    checksum=saved.checksum,
                    size_bytes=saved.size_bytes,
                    content_type="application/json",
                )
                session.add(artifact)
                session.execute(
                    update(Investigation)
                    .where(Investigation.id == item.id)
                    .values(status=Status.CREATED, source_metadata={"format": "DatasetBundle"})
                )
            return artifact
        except Exception:
            if saved:
                self.storage.delete(saved.key)
            raise

    def _lock_idle(self, session, investigation_id: str, target: Status):
        changed = session.execute(
            update(Investigation)
            .where(
                Investigation.id == investigation_id,
                Investigation.status.not_in([Status.QUEUED, Status.RUNNING, Status.UPLOADING]),
            )
            .values(status=target, updated_at=utcnow())
        )
        if changed.rowcount != 1:
            raise ProductError("CONFLICT")

    def start(
        self, principal: Principal, investigation_id: str, artifact_id: str, idempotency_key: str
    ) -> AnalysisRun:
        try:
            with self._write() as session:
                self._owned(session, principal, investigation_id)
                existing = session.scalar(
                    select(AnalysisRun).where(
                        AnalysisRun.investigation_id == investigation_id,
                        AnalysisRun.idempotency_key == idempotency_key,
                    )
                )
                if existing:
                    if existing.artifact_id != artifact_id:
                        raise ProductError("CONFLICT")
                    return existing
                artifact = session.get(Artifact, artifact_id)
                if artifact is None or artifact.investigation_id != investigation_id:
                    raise ProductError("NOT_FOUND")
                self._quota(
                    session,
                    AnalysisRun,
                    self.settings.max_runs_per_investigation,
                    AnalysisRun.investigation_id == investigation_id,
                )
                self._quota(
                    session,
                    AnalysisRun,
                    self.settings.max_pending_runs,
                    AnalysisRun.status.in_([Status.QUEUED, Status.RUNNING]),
                )
                self._lock_idle(session, investigation_id, Status.QUEUED)
                run = AnalysisRun(
                    investigation_id=investigation_id,
                    artifact_id=artifact.id,
                    status=Status.QUEUED,
                    active_slot=investigation_id,
                    idempotency_key=idempotency_key,
                    version_metadata={
                        "application": __version__,
                        "detector": "phase3-network-hgb",
                        "build_commit": self.settings.build_commit,
                        "configuration_schema": "1",
                        "result_schema": "1",
                    },
                    configuration_snapshot={
                        "training_seeds": [102, 103, 104],
                        "validation_seed": 101,
                        "model_random_state": 105,
                        "transactions_per_seed": 5000,
                        "input_checksum": artifact.checksum,
                        "timeout_seconds": self.settings.analysis_timeout_seconds,
                    },
                )
                session.add(run)
            return run
        except IntegrityError:
            raise ProductError("CONFLICT") from None

    def runs(self, principal: Principal, investigation_id: str) -> list[AnalysisRun]:
        with self.database.session() as session:
            self._owned(session, principal, investigation_id)
            return list(
                session.scalars(
                    select(AnalysisRun)
                    .where(AnalysisRun.investigation_id == investigation_id)
                    .order_by(AnalysisRun.created_at, AnalysisRun.id)
                )
            )

    def run(self, principal: Principal, run_id: str) -> AnalysisRun:
        with self.database.session() as session:
            run = session.scalar(
                select(AnalysisRun)
                .join(Investigation)
                .where(AnalysisRun.id == run_id, Investigation.owner_id == principal.user_id)
            )
            if run is None:
                raise ProductError("NOT_FOUND")
            return run

    def result(self, principal: Principal, run_id: str) -> dict:
        run = self.run(principal, run_id)
        if run.status != Status.COMPLETED or not run.result_reference:
            raise ProductError("CONFLICT")
        content = self.storage.read(run.result_reference)
        if hashlib.sha256(content).hexdigest() != run.result_checksum:
            raise ProductError("INTERNAL_ERROR")
        return json.loads(content)

    def claim(self) -> str | None:
        with self.database.session.begin() as session:
            run = session.scalar(
                select(AnalysisRun)
                .where(AnalysisRun.status == Status.QUEUED)
                .order_by(AnalysisRun.created_at, AnalysisRun.id)
                .limit(1)
            )
            if run is None:
                return None
            result = session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == run.id, AnalysisRun.status == Status.QUEUED)
                .values(status=Status.RUNNING, started_at=utcnow())
            )
            if result.rowcount != 1:
                return None
            session.execute(
                update(Investigation)
                .where(Investigation.id == run.investigation_id)
                .values(status=Status.RUNNING)
            )
            return run.id

    def finish(self, run_id: str, result: dict | None = None, error_code: str | None = None):
        saved = None
        try:
            if result is not None:
                content = json.dumps(
                    result, sort_keys=True, allow_nan=False, separators=(",", ":")
                ).encode()
                if len(content) > self.settings.result_limit_bytes:
                    raise ProductError("QUOTA_EXCEEDED")
                saved = self.storage.save(content)
            with self.database.session.begin() as session:
                run = session.get(AnalysisRun, run_id)
                if run is None or run.status != Status.RUNNING:
                    raise ProductError("CONFLICT")
                status = Status.FAILED if error_code else Status.COMPLETED
                if not error_code and saved is None:
                    raise ValueError("Successful runs require a result")
                run.status, run.active_slot, run.completed_at = status, None, utcnow()
                run.error_code = error_code
                run.error_message_safe = ERRORS[error_code][1] if error_code else None
                run.result_reference = saved.key if saved else None
                run.result_checksum = saved.checksum if saved else None
                session.execute(
                    update(Investigation)
                    .where(Investigation.id == run.investigation_id)
                    .values(status=status)
                )
        except Exception:
            if saved:
                self.storage.delete(saved.key)
            raise

    def recover_interrupted(self):
        # SINGLE scheduler only. Queued work survives; crashed running work is not auto-retried.
        with self.database.session() as session:
            ids = list(
                session.scalars(select(AnalysisRun.id).where(AnalysisRun.status == Status.RUNNING))
            )
        for run_id in ids:
            self.finish(run_id, error_code="WORKER_INTERRUPTED")
