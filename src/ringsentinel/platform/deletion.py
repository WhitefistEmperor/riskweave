"""Owner-scoped erasure with durable, idempotent cleanup of unreferenced objects."""

import argparse
import json
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import DatabaseStorageBackend, storage_for
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import (
    AnalysisRun,
    Artifact,
    CandidateReview,
    Investigation,
    ReviewAudit,
    Status,
    StorageDeletion,
    utcnow,
)
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.settings import Settings

logger = logging.getLogger("ringsentinel.cleanup")
ACTIVE = (Status.QUEUED, Status.RUNNING, Status.UPLOADING)


def retention_conditions(cutoff: datetime):
    active_runs = (
        select(AnalysisRun.id)
        .where(
            AnalysisRun.investigation_id == Investigation.id,
            (AnalysisRun.status.in_(ACTIVE)) | (AnalysisRun.active_slot.is_not(None)),
        )
        .exists()
    )
    open_reviews = (
        select(CandidateReview.run_id)
        .join(AnalysisRun)
        .where(
            AnalysisRun.investigation_id == Investigation.id,
            CandidateReview.disposition.in_(["investigating", "escalated"]),
        )
        .exists()
    )
    return (
        Investigation.updated_at < cutoff,
        Investigation.status.not_in(ACTIVE),
        ~active_runs,
        ~open_reviews,
    )


class DeletionService:
    def __init__(self, service: InvestigationService):
        self.service = service

    def remove(
        self,
        principal: Principal,
        investigation_id: str,
        confirm_name: str,
        expected_updated_at: datetime | None = None,
        *,
        older_than: datetime | None = None,
    ) -> dict:
        with self.service._write() as session:
            item = self.service._owned(session, principal, investigation_id)
            if item.name != confirm_name or item.status in ACTIVE:
                raise ProductError("CONFLICT")
            updated = (
                item.updated_at.replace(tzinfo=UTC)
                if item.updated_at.tzinfo is None
                else item.updated_at
            )
            if expected_updated_at is not None and updated != expected_updated_at:
                raise ProductError("CONFLICT")
            if (
                older_than is not None
                and session.scalar(
                    select(Investigation.id).where(
                        Investigation.id == item.id, *retention_conditions(older_than)
                    )
                )
                is None
            ):
                raise ProductError("CONFLICT")
            runs = list(
                session.scalars(select(AnalysisRun).where(AnalysisRun.investigation_id == item.id))
            )
            if any(run.status in ACTIVE or run.active_slot is not None for run in runs):
                raise ProductError("CONFLICT")
            artifacts = list(
                session.scalars(select(Artifact).where(Artifact.investigation_id == item.id))
            )
            keys = {artifact.storage_key for artifact in artifacts}
            keys.update(run.result_reference for run in runs if run.result_reference)
            if any(not re.fullmatch(r"[a-f0-9]{32}\.json", key) for key in keys):
                raise ProductError("INTERNAL_ERROR")
            # A corrupt shared reference must never erase another investigation's bytes.
            if keys and (
                session.scalar(
                    select(Artifact.id)
                    .where(Artifact.storage_key.in_(keys), Artifact.investigation_id != item.id)
                    .limit(1)
                )
                or session.scalar(
                    select(AnalysisRun.id)
                    .where(
                        AnalysisRun.result_reference.in_(keys),
                        AnalysisRun.investigation_id != item.id,
                    )
                    .limit(1)
                )
            ):
                raise ProductError("INTERNAL_ERROR")
            for key in keys:
                if isinstance(self.service.storage, DatabaseStorageBackend):
                    self.service.storage.delete_in(session, key)
                elif session.get(StorageDeletion, key) is None:
                    session.add(StorageDeletion(key=key))
            run_ids = select(AnalysisRun.id).where(AnalysisRun.investigation_id == item.id)
            session.execute(delete(ReviewAudit).where(ReviewAudit.run_id.in_(run_ids)))
            session.execute(delete(CandidateReview).where(CandidateReview.run_id.in_(run_ids)))
            session.execute(delete(AnalysisRun).where(AnalysisRun.investigation_id == item.id))
            session.execute(delete(Artifact).where(Artifact.investigation_id == item.id))
            session.execute(delete(Investigation).where(Investigation.id == item.id))
        # Database commit precedes file removal. Failure/crash leaves retryable work.
        try:
            self.cleanup(keys=keys)
            with self.service.database.session() as session:
                pending = bool(
                    keys
                    and session.scalar(
                        select(StorageDeletion.key).where(StorageDeletion.key.in_(keys)).limit(1)
                    )
                )
        except Exception:
            # Erasure has committed. Never report a failed request that could recreate data.
            pending = bool(keys)
            logger.error(json.dumps({"event": "storage_cleanup_unavailable"}))
        return {
            "investigation_id": investigation_id,
            "status": "deleted",
            "storage_cleanup": "pending" if pending else "complete",
        }

    def cleanup(self, *, keys: set[str] | None = None, limit: int = 100) -> dict:
        if not 1 <= limit <= 1000:
            raise ValueError("Cleanup batch must contain between 1 and 1000 objects")
        if keys is not None and not keys:
            return {"removed": 0, "pending": 0}
        removed = 0
        with self.service._write() as session:
            query = select(StorageDeletion).order_by(
                StorageDeletion.last_attempt_at.asc().nulls_first(),
                StorageDeletion.created_at,
                StorageDeletion.key,
            )
            if keys is not None:
                query = query.where(StorageDeletion.key.in_(keys))
            for task in session.scalars(query.limit(limit)):
                task.attempts += 1
                task.last_attempt_at = utcnow()
                referenced = session.scalar(
                    select(Artifact.id).where(Artifact.storage_key == task.key).limit(1)
                ) or session.scalar(
                    select(AnalysisRun.id).where(AnalysisRun.result_reference == task.key).limit(1)
                )
                if referenced:
                    task.last_error_code = "REFERENCED_OBJECT"
                    logger.error(json.dumps({"event": "storage_cleanup_reference_conflict"}))
                    continue
                try:
                    if isinstance(self.service.storage, DatabaseStorageBackend):
                        self.service.storage.delete_in(session, task.key)
                    else:
                        self.service.storage.delete(task.key)
                except (OSError, RuntimeError, ValueError, ProductError) as failure:
                    task.last_error_code = (
                        "UNSAFE_LOCATION"
                        if isinstance(failure, ValueError)
                        else "STORAGE_UNAVAILABLE"
                    )
                    logger.warning(json.dumps({"event": "storage_cleanup_retry_pending"}))
                    continue
                session.delete(task)
                removed += 1
            session.flush()
            remaining = select(func.count()).select_from(StorageDeletion)
            if keys is not None:
                remaining = remaining.where(StorageDeletion.key.in_(keys))
            pending = session.scalar(remaining)
        return {"removed": removed, "pending": pending}


def main():
    parser = argparse.ArgumentParser(description="Retry committed investigation file cleanup")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    database = None
    try:
        settings = Settings()
        database = Database(settings.database_url.get_secret_value())
        service = InvestigationService(
            database,
            storage_for(database, settings),
            settings,
        )
        result = DeletionService(service).cleanup(limit=args.limit)
        print(json.dumps(result, sort_keys=True))
        if result["pending"]:
            parser.exit(2, "Some objects still await cleanup; inspect private operator logs.\n")
    except Exception:
        parser.exit(1, "Cleanup unavailable; check configuration and private operator logs.\n")
    finally:
        if database is not None:
            database.engine.dispose()


if __name__ == "__main__":
    main()
