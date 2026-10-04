"""Private read-only operator snapshot; no case identifiers, tokens or mutations."""

import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select, text

from ringsentinel.platform.database import Database
from ringsentinel.platform.models import AnalysisDispatch, AnalysisRun, Status, utcnow
from ringsentinel.platform.settings import Settings


def report(database: Database):
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
    return {
        "status": "attention" if alerts else "ok",
        "schema_revision": revision,
        "observed_at": now.isoformat(),
        "run_counts": counts,
        "overdue_runs": overdue,
        "failed_last_24_hours": failed,
        "delivery_overdue_5_minutes": delayed,
        "alerts": alerts,
        "automatic_recovery": False,
    }


def main():
    database = None
    try:
        settings = Settings()
        database = Database(settings.database_url.get_secret_value())
        result = report(database)
    except Exception:
        result = {"status": "unavailable", "alerts": ["OPERATOR_REPORT_UNAVAILABLE"]}
    finally:
        if database is not None:
            database.engine.dispose()
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "ok" else 1 if result["status"] == "attention" else 2)


if __name__ == "__main__":
    main()
