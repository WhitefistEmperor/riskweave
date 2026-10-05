"""Owner-scoped transactional application service, independent of HTTP and execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, timedelta
from pathlib import PurePosixPath

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from ringsentinel import __version__
from ringsentinel.data.ingestion import PaymentDataset, parse_input
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import DatabaseStorageBackend
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

    def _write(self):
        return self.database.write()

    def _save(self, session, content: bytes):
        if isinstance(self.storage, DatabaseStorageBackend):
            return self.storage.save_in(session, content)
        return self.storage.save(content)

    def _discard_uncommitted(self, saved):
        # Database bytes have already rolled back with their metadata.
        if saved and not isinstance(self.storage, DatabaseStorageBackend):
            self.storage.delete(saved.key)

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
        if self.settings.execution_mode == "request":
            self.expire_deadlines(principal=principal)
            from ringsentinel.platform.upload_transport import UploadTransport

            if isinstance(self.storage, DatabaseStorageBackend):
                UploadTransport(self).expire(principal=principal)
        with self.database.session() as session:
            return list(
                session.scalars(
                    select(Investigation)
                    .where(Investigation.owner_id == principal.user_id)
                    .order_by(Investigation.created_at, Investigation.id)
                )
            )

    def page(self, principal: Principal, *, offset=0, limit=10, search="", status=None):
        if self.settings.execution_mode == "request":
            self.expire_deadlines(principal=principal)
            from ringsentinel.platform.upload_transport import UploadTransport

            if isinstance(self.storage, DatabaseStorageBackend):
                UploadTransport(self).expire(principal=principal)
        conditions = [Investigation.owner_id == principal.user_id]
        lower = (
            func.riskweave_lower if self.database.engine.dialect.name == "sqlite" else func.lower
        )
        needle = search.strip().lower()
        if needle:
            # User wildcards are literal, not permission to match the whole worklist.
            pattern = "%" + needle.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
            conditions.append(
                or_(
                    lower(Investigation.name).like(pattern, escape="!"),
                    lower(Investigation.id).like(pattern, escape="!"),
                )
            )
        if status is not None:
            conditions.append(Investigation.status == status)
        with self.database.session() as session:
            total = session.scalar(
                select(func.count())
                .select_from(Investigation)
                .where(Investigation.owner_id == principal.user_id)
            )
            matched = session.scalar(
                select(func.count()).select_from(Investigation).where(*conditions)
            )
            items = list(
                session.scalars(
                    select(Investigation)
                    .where(*conditions)
                    .order_by(Investigation.updated_at.desc(), Investigation.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            from ringsentinel.platform.worklist_reviews import summaries

            return dict(
                items=items,
                total=total,
                matched=matched,
                offset=offset,
                limit=limit,
                review_summaries=summaries(session, items),
            )

    def get(self, principal: Principal, investigation_id: str) -> Investigation:
        with self.database.session() as session:
            item = self._owned(session, principal, investigation_id)
        if self.settings.execution_mode == "request":
            self.expire_deadlines(principal=principal, investigation_id=investigation_id)
            from ringsentinel.platform.upload_transport import UploadTransport

            if isinstance(self.storage, DatabaseStorageBackend):
                UploadTransport(self).expire(principal=principal, investigation_id=investigation_id)
            with self.database.session() as session:
                return self._owned(session, principal, investigation_id)
        return item

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
            bundle = parse_input(content)
            if not bundle.events:
                raise ValueError("Empty dataset")
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProductError("INVALID_DATASET") from None
        checksum = hashlib.sha256(content).hexdigest()
        saved = None
        try:
            with self._write() as session:
                artifact, saved = self.attach_validated_in(
                    session, principal, investigation_id, content, name, bundle, checksum
                )
            return artifact
        except Exception:
            self._discard_uncommitted(saved)
            raise

    def attach_validated_in(
        self,
        session,
        principal: Principal,
        investigation_id: str,
        content: bytes,
        name: str,
        bundle,
        checksum: str,
        *,
        reserved_upload=None,
    ):
        """Commit validated bytes and metadata in the caller's write transaction."""
        item = self._owned(session, principal, investigation_id)
        if reserved_upload is None:
            previous_status = item.status
            self._lock_idle(session, item.id, Status.UPLOADING)
        else:
            if item.status != Status.UPLOADING or reserved_upload.active_slot != item.id:
                raise ProductError("CONFLICT")
            previous_status = reserved_upload.previous_status
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
            return existing, None
        self._quota(
            session,
            Artifact,
            self.settings.max_artifacts_per_investigation,
            Artifact.investigation_id == item.id,
        )
        saved = self._save(session, content)
        try:
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
                .values(
                    status=Status.CREATED,
                    source_metadata={
                        "format": "payments-v1"
                        if isinstance(bundle, PaymentDataset)
                        else "DatasetBundle",
                        "labels_available": not isinstance(bundle, PaymentDataset),
                    },
                )
            )
        except Exception:
            self._discard_uncommitted(saved)
            raise
        return artifact, saved

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
                if self.settings.execution_mode == "request":
                    self._expire_in(session, principal=principal, investigation_id=investigation_id)
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
                        "model_artifact_sha256": self.settings.model_artifact_sha256
                        or "runtime-trained",
                    },
                    configuration_snapshot={
                        "training_seeds": [102, 103, 104],
                        "validation_seed": 101,
                        "model_random_state": 105,
                        "transactions_per_seed": 5000,
                        "input_checksum": artifact.checksum,
                        "timeout_seconds": self.settings.analysis_timeout_seconds,
                        "execution_mode": self.settings.execution_mode,
                        "background_dispatch": self.settings.background_dispatch,
                    },
                    execution_deadline=utcnow() + timedelta(hours=24)
                    if self.settings.execution_mode == "request"
                    else None,
                )
                session.add(run)
                if self.settings.background_dispatch == "vercel_workflow":
                    from ringsentinel.platform.dispatch import reserve_dispatch

                    session.flush()
                    reserve_dispatch(session, run, self.settings)
            return run
        except IntegrityError:
            raise ProductError("CONFLICT") from None

    def runs(self, principal: Principal, investigation_id: str) -> list[AnalysisRun]:
        self.get(principal, investigation_id)
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
        if self.settings.execution_mode == "request":
            self.expire_deadlines(run_id=run_id)
            with self.database.session() as session:
                run = session.get(AnalysisRun, run_id)
                if run is None:
                    raise ProductError("NOT_FOUND")
                return run
        return run

    def result(self, principal: Principal, run_id: str, *, max_bytes: int | None = None) -> dict:
        return json.loads(self.result_content(principal, run_id, max_bytes=max_bytes))

    def result_content(
        self, principal: Principal, run_id: str, *, max_bytes: int | None = None
    ) -> bytes:
        """Authorize and verify immutable bytes before any result transport."""
        run = self.run(principal, run_id)
        if run.status != Status.COMPLETED or not run.result_reference:
            raise ProductError("CONFLICT")
        if max_bytes is not None and self.storage.size(run.result_reference) > max_bytes:
            raise ProductError("RESULT_TRANSPORT_REQUIRED")
        content = self.storage.read(run.result_reference)
        if hashlib.sha256(content).hexdigest() != run.result_checksum:
            raise ProductError("INTERNAL_ERROR")
        return content

    def claim(self, run_id: str | None = None, principal: Principal | None = None) -> str | None:
        with self._write() as session:
            query = select(AnalysisRun).where(AnalysisRun.status == Status.QUEUED)
            if run_id is not None:
                if principal is None:
                    raise ValueError("Targeted claims require an owner")
                query = query.join(Investigation).where(
                    AnalysisRun.id == run_id, Investigation.owner_id == principal.user_id
                )
            if self.settings.execution_mode == "request" and session.scalar(
                select(AnalysisRun.id).where(AnalysisRun.status == Status.RUNNING).limit(1)
            ):
                return None
            run = session.scalar(query.order_by(AnalysisRun.created_at, AnalysisRun.id).limit(1))
            if run is None:
                return None
            now = utcnow()
            values = {"status": Status.RUNNING, "started_at": now}
            if self.settings.execution_mode == "request":
                # The child watchdog ends at timeout+5; allow persistence/parent cleanup
                # before another invocation can release its capacity slot.
                values.update(
                    execution_deadline=now
                    + timedelta(seconds=self.settings.analysis_timeout_seconds + 20),
                    executor_slot="request-analysis",
                )
            result = session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == run.id, AnalysisRun.status == Status.QUEUED)
                .values(**values)
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
            content = None
            if result is not None:
                content = json.dumps(
                    result, sort_keys=True, allow_nan=False, separators=(",", ":")
                ).encode()
                if len(content) > self.settings.result_limit_bytes:
                    raise ProductError("QUOTA_EXCEEDED")
            with self._write() as session:
                run = session.get(AnalysisRun, run_id)
                if run is None or run.status != Status.RUNNING:
                    raise ProductError("CONFLICT")
                deadline = run.execution_deadline
                if deadline and deadline.replace(tzinfo=UTC) <= utcnow():
                    error_code = "ANALYSIS_TIMEOUT"
                if content is not None and not error_code:
                    saved = self._save(session, content)
                status = Status.FAILED if error_code else Status.COMPLETED
                if not error_code and saved is None:
                    raise ValueError("Successful runs require a result")
                run.status, run.active_slot, run.completed_at = status, None, utcnow()
                run.execution_deadline, run.executor_slot = None, None
                run.error_code = error_code
                run.error_message_safe = ERRORS[error_code][1] if error_code else None
                run.result_reference = saved.key if saved else None
                run.result_checksum = saved.checksum if saved else None
                run.result_size_bytes = saved.size_bytes if saved else None
                if saved:
                    from ringsentinel.platform.worklist_reviews import candidate_count

                    run.candidate_count = candidate_count(result)
                    from ringsentinel.platform.result_fragments import index_in

                    index_in(session, run, content)
                    from ringsentinel.platform.result_sections import index_in as index_sections

                    index_sections(session, run, result, content)
                session.execute(
                    update(Investigation)
                    .where(Investigation.id == run.investigation_id)
                    .values(status=status)
                )
        except Exception:
            self._discard_uncommitted(saved)
            raise

    def expire_deadlines(
        self,
        *,
        run_id: str | None = None,
        principal: Principal | None = None,
        investigation_id: str | None = None,
        limit: int = 100,
    ) -> int:
        """Fence expired work without failing healthy invocations in another instance."""
        if not 1 <= limit <= 1000:
            raise ValueError("Invalid recovery batch")
        with self._write() as session:
            return self._expire_in(
                session,
                run_id=run_id,
                principal=principal,
                investigation_id=investigation_id,
                limit=limit,
            )

    def _expire_in(
        self, session, *, run_id=None, principal=None, investigation_id=None, limit=100
    ) -> int:
        query = select(AnalysisRun).where(
            AnalysisRun.status.in_([Status.QUEUED, Status.RUNNING]),
            AnalysisRun.execution_deadline <= utcnow(),
        )
        if run_id is not None:
            query = query.where(AnalysisRun.id == run_id)
        if investigation_id is not None:
            query = query.where(AnalysisRun.investigation_id == investigation_id)
        if principal is not None:
            query = query.join(Investigation).where(Investigation.owner_id == principal.user_id)
        expired = list(
            session.scalars(
                query.order_by(AnalysisRun.execution_deadline, AnalysisRun.id).limit(limit)
            )
        )
        for run in expired:
            run.error_code = (
                "WORKER_INTERRUPTED" if run.status == Status.RUNNING else "QUEUE_EXPIRED"
            )
            run.error_message_safe = ERRORS[run.error_code][1]
            run.status, run.active_slot, run.executor_slot = Status.FAILED, None, None
            run.completed_at, run.execution_deadline = utcnow(), None
            session.execute(
                update(Investigation)
                .where(Investigation.id == run.investigation_id)
                .values(status=Status.FAILED, updated_at=utcnow())
            )
        return len(expired)

    def recover_interrupted(self):
        # SINGLE scheduler only. Queued work survives; crashed running work is not auto-retried.
        with self.database.session() as session:
            ids = list(
                session.scalars(select(AnalysisRun.id).where(AnalysisRun.status == Status.RUNNING))
            )
        for run_id in ids:
            self.finish(run_id, error_code="WORKER_INTERRUPTED")
