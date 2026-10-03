"""Analyst decisions are separate from immutable model results."""

from sqlalchemy import select

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import (
    AnalysisRun,
    CandidateReview,
    ReviewAudit,
    ReviewDisposition,
    utcnow,
)
from ringsentinel.platform.service import InvestigationService, Principal


class ReviewService:
    def __init__(self, investigations: InvestigationService):
        self.investigations = investigations

    def _candidate(self, principal: Principal, run_id: str, candidate_id: str):
        result = self.investigations.result(principal, run_id)
        if not any(ring["candidate"]["candidate_id"] == candidate_id for ring in result["rings"]):
            raise ProductError("NOT_FOUND")

    @staticmethod
    def _response(session, run_id: str, candidate_id: str) -> dict:
        review = session.get(CandidateReview, (run_id, candidate_id))
        history = list(
            session.scalars(
                select(ReviewAudit)
                .where(ReviewAudit.run_id == run_id, ReviewAudit.candidate_id == candidate_id)
                .order_by(ReviewAudit.version)
            )
        )
        return {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "disposition": review.disposition if review else ReviewDisposition.UNREVIEWED,
            "version": review.version if review else 0,
            "updated_at": review.updated_at if review else None,
            "history": history,
        }

    def get(self, principal: Principal, run_id: str, candidate_id: str) -> dict:
        self._candidate(principal, run_id, candidate_id)
        with self.investigations.database.session() as session:
            return self._response(session, run_id, candidate_id)

    def save(
        self,
        principal: Principal,
        run_id: str,
        candidate_id: str,
        disposition: ReviewDisposition,
        note: str,
        expected_version: int,
        idempotency_key: str,
    ) -> dict:
        self._candidate(principal, run_id, candidate_id)
        # This lock also serializes the initial insert across processes/databases.
        with self.investigations._write() as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                raise ProductError("NOT_FOUND")
            investigation = self.investigations._owned(session, principal, run.investigation_id)
            existing = session.scalar(
                select(ReviewAudit).where(
                    ReviewAudit.run_id == run_id,
                    ReviewAudit.candidate_id == candidate_id,
                    ReviewAudit.idempotency_key == idempotency_key,
                )
            )
            if existing:
                if (
                    existing.disposition != disposition
                    or existing.note != note
                    or existing.version != expected_version + 1
                ):
                    raise ProductError("CONFLICT")
                return self._response(session, run_id, candidate_id)
            review = session.get(CandidateReview, (run_id, candidate_id))
            version = review.version if review else 0
            if version != expected_version:
                raise ProductError("CONFLICT")
            self.investigations._quota(
                session,
                ReviewAudit,
                self.investigations.settings.max_review_events_per_candidate,
                ReviewAudit.run_id == run_id,
                ReviewAudit.candidate_id == candidate_id,
            )
            previous = review.disposition if review else ReviewDisposition.UNREVIEWED
            if review is None:
                review = CandidateReview(run_id=run_id, candidate_id=candidate_id)
                session.add(review)
            review.disposition = disposition
            review.version = version + 1
            review.updated_at = utcnow()
            investigation.updated_at = review.updated_at
            session.flush()  # Insert the composite parent before the audit foreign key.
            session.add(
                ReviewAudit(
                    run_id=run_id,
                    candidate_id=candidate_id,
                    actor_id=principal.user_id,
                    previous_disposition=previous,
                    disposition=disposition,
                    version=version + 1,
                    note=note,
                    idempotency_key=idempotency_key,
                )
            )
            session.flush()
            return self._response(session, run_id, candidate_id)
