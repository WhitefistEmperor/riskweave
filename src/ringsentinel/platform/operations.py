"""Private read-only operator snapshot; no case identifiers, tokens or mutations."""

import argparse
import json
from datetime import UTC, timedelta
from pathlib import Path

from sqlalchemy import func, select, text

from ringsentinel.platform.database import Database
from ringsentinel.platform.models import (
    AnalysisDispatch,
    AnalysisRun,
    Status,
    StorageDeletion,
    utcnow,
)
from ringsentinel.platform.settings import Settings


def report(database: Database, *, queue_wait_minutes: int = 30, cleanup_wait_minutes: int = 30):
    if any(
        type(value) is not int or not 1 <= value <= 1440
        for value in (queue_wait_minutes, cleanup_wait_minutes)
    ):
        raise ValueError("Monitoring wait thresholds must be whole minutes between 1 and 1440")
    if database.engine.dialect.name == "sqlite":
        path = database.engine.url.database
        if path != ":memory:" and (not path or not Path(path).is_file()):
            raise ValueError("An existing migrated database is required")
    now = utcnow()
    with database.session() as session:
        if database.engine.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != Database.revision:
            raise ValueError("Operator report requires the current schema")
        counts = {status.value: 0 for status in Status}
        for status, count in session.execute(
            select(AnalysisRun.status, func.count()).group_by(AnalysisRun.status)
        ):
            counts[status.value] = count
        oldest_queued = session.scalar(
            select(func.min(AnalysisRun.created_at)).where(AnalysisRun.status == Status.QUEUED)
        )
        stalled_queue = session.scalar(
            select(func.count())
            .select_from(AnalysisRun)
            .where(
                AnalysisRun.status == Status.QUEUED,
                AnalysisRun.created_at < now - timedelta(minutes=queue_wait_minutes),
            )
        )
        pending_cleanup, oldest_cleanup = session.execute(
            select(func.count(), func.min(StorageDeletion.created_at)).select_from(StorageDeletion)
        ).one()
        stalled_cleanup = session.scalar(
            select(func.count())
            .select_from(StorageDeletion)
            .where(StorageDeletion.created_at < now - timedelta(minutes=cleanup_wait_minutes))
        )
        overdue = session.scalar(
            select(func.count())
            .select_from(AnalysisRun)
            .where(
                AnalysisRun.status.in_([Status.QUEUED, Status.RUNNING]),
                AnalysisRun.execution_deadline < now,
            )
        )
        failed = session.scalar(
            select(func.count())
            .select_from(AnalysisRun)
            .where(
                AnalysisRun.status == Status.FAILED,
                AnalysisRun.completed_at >= now - timedelta(hours=24),
            )
        )
        delayed = session.scalar(
            select(func.count())
            .select_from(AnalysisDispatch)
            .join(
                AnalysisRun,
                AnalysisRun.id == AnalysisDispatch.run_id,
            )
            .where(
                AnalysisRun.status == Status.QUEUED,
                AnalysisDispatch.next_attempt_at < now - timedelta(minutes=5),
            )
        )
    alerts = []
    if overdue:
        alerts.append("EXECUTION_DEADLINE_EXCEEDED")
    if failed:
        alerts.append("RECENT_ANALYSIS_FAILURE")
    if delayed:
        alerts.append("DELIVERY_RECONCILIATION_OVERDUE")
    if stalled_queue:
        alerts.append("QUEUE_WAIT_EXCEEDED")
    if stalled_cleanup:
        alerts.append("STORAGE_CLEANUP_OVERDUE")

    def age_seconds(timestamp):
        if timestamp is None:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return max(0, int((now - timestamp).total_seconds()))

    return {
        "status": "attention" if alerts else "ok",
        "schema_revision": revision,
        "observed_at": now.isoformat(),
        "run_counts": counts,
        "overdue_runs": overdue,
        "failed_last_24_hours": failed,
        "delivery_overdue_5_minutes": delayed,
        "queue_wait_minutes": queue_wait_minutes,
        "queued_wait_exceeded": stalled_queue,
        "oldest_queued_seconds": age_seconds(oldest_queued),
        "cleanup_wait_minutes": cleanup_wait_minutes,
        "pending_storage_deletions": pending_cleanup,
        "storage_cleanup_overdue": stalled_cleanup,
        "oldest_pending_deletion_seconds": age_seconds(oldest_cleanup),
        "alerts": alerts,
        "automatic_recovery": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-wait-minutes", type=int, default=30)
    parser.add_argument("--cleanup-wait-minutes", type=int, default=30)
    args = parser.parse_args()
    database = None
    try:
        settings = Settings()
        database = Database(settings.database_url.get_secret_value())
        result = report(
            database,
            queue_wait_minutes=args.queue_wait_minutes,
            cleanup_wait_minutes=args.cleanup_wait_minutes,
        )
    except Exception:
        result = {"status": "unavailable", "alerts": ["OPERATOR_REPORT_UNAVAILABLE"]}
    finally:
        if database is not None:
            database.engine.dispose()
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "ok" else 1 if result["status"] == "attention" else 2)


if __name__ == "__main__":
    main()
