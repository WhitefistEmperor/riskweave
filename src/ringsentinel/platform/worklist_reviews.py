"""Bounded metadata-only review summaries for an already owner-scoped page."""

from sqlalchemy import func, select

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import AnalysisRun, CandidateReview, Status


def summaries(session, items):
    result = {item.id: None for item in items}
    if not result:
        return result
    latest = (
        select(
            AnalysisRun.id,
            AnalysisRun.investigation_id,
            AnalysisRun.candidate_count,
            func.row_number()
            .over(
                partition_by=AnalysisRun.investigation_id,
                order_by=(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()),
            )
            .label("position"),
        )
        .where(AnalysisRun.investigation_id.in_(result), AnalysisRun.status == Status.COMPLETED)
        .subquery()
    )
    runs = session.execute(select(latest).where(latest.c.position == 1)).all()
    run_ids = [run.id for run in runs]
    counts = {}
    if run_ids:
        rows = session.execute(
            select(CandidateReview.run_id, CandidateReview.disposition, func.count())
            .where(CandidateReview.run_id.in_(run_ids))
            .group_by(CandidateReview.run_id, CandidateReview.disposition)
        ).all()
        counts = {(run_id, disposition): count for run_id, disposition, count in rows}
    for run in runs:
        dispositions = {
            name: counts.get((run.id, name), 0)
            for name in ("investigating", "escalated", "dismissed")
        }
        assessed = sum(dispositions.values())
        if run.candidate_count is not None and (
            run.candidate_count < assessed or run.candidate_count < 0
        ):
            raise ProductError("INTERNAL_ERROR")
        result[run.investigation_id] = dict(
            run_id=run.id,
            candidate_count=run.candidate_count,
            assessed=assessed,
            unreviewed=None if run.candidate_count is None else run.candidate_count - assessed,
            **dispositions,
        )
    return result


def candidate_count(result):
    rings = result.get("rings")
    if not isinstance(rings, list):
        return None
    ids = []
    for ring in rings:
        if not isinstance(ring, dict) or not isinstance(ring.get("candidate"), dict):
            return None
        value = ring["candidate"].get("candidate_id")
        if not isinstance(value, str) or not value:
            return None
        ids.append(value)
    return len(ids) if len(set(ids)) == len(ids) else None
