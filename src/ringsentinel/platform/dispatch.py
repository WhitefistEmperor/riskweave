"""Transactional delivery intent, bounded leases/retries and a monthly start budget."""

import asyncio
import re
from datetime import UTC, timedelta
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select, update

from ringsentinel.platform.errors import ERRORS, ProductError
from ringsentinel.platform.models import (
    AnalysisDispatch,
    AnalysisRun,
    DispatchBudget,
    DispatchSchedule,
    Investigation,
    Status,
    utcnow,
)
from ringsentinel.platform.service import Principal

MAX_START_ATTEMPTS = 3
LEASE_SECONDS = 30
PUBLISH_SECONDS = 10
WORKFLOW_ID = re.compile(r"^wrun_[A-Za-z0-9]{26}$")


class WorkflowDelivery(Protocol):
    async def analysis(self, run_id: str, ticket: str) -> str: ...
    async def reconcile(self) -> str: ...
    async def status(self, workflow_id: str) -> str: ...


def _reserve_budget(session, settings):
    month = utcnow().strftime("%Y-%m")
    budget = session.get(DispatchBudget, month)
    if budget is None:
        budget = DispatchBudget(month=month, starts=0)
        session.add(budget)
    if budget.starts >= settings.dispatch_starts_per_month:
        raise ProductError("QUOTA_EXCEEDED")
    budget.starts += 1
    return month


def reserve_dispatch(session, run, settings):
    """The caller holds Database.write(): quota, run and intent commit together."""
    month = _reserve_budget(session, settings)
    session.add(AnalysisDispatch(run_id=run.id, ticket=str(uuid4()), budget_month=month))
    run.dispatch_state = "pending"


def fail_queued(session, run, code):
    if run.status != Status.QUEUED:
        return
    run.status, run.dispatch_state = Status.FAILED, "failed"
    run.error_code, run.error_message_safe = code, ERRORS[code][1]
    run.active_slot, run.executor_slot, run.execution_deadline = None, None, None
    run.completed_at = utcnow()
    session.execute(
        update(Investigation)
        .where(Investigation.id == run.investigation_id)
        .values(status=Status.FAILED, updated_at=utcnow())
    )


class DeliveryCoordinator:
    def __init__(self, service, delivery: WorkflowDelivery):
        self.service, self.delivery = service, delivery

    def _claim(self, run_id):
        with self.service._write() as session:
            run = session.get(AnalysisRun, run_id)
            item = session.get(AnalysisDispatch, run_id)
            now = utcnow()
            if (
                run is None
                or item is None
                or run.status != Status.QUEUED
                or item.workflow_id
                or item.next_attempt_at.replace(tzinfo=UTC) > now
                or item.lease_until
                and item.lease_until.replace(tzinfo=UTC) > now
            ):
                return None
            if item.attempts >= MAX_START_ATTEMPTS:
                fail_queued(session, run, "DISPATCH_FAILED")
                return None
            if item.attempts or item.budget_month != now.strftime("%Y-%m"):
                try:
                    _reserve_budget(session, self.service.settings)
                except ProductError:
                    fail_queued(session, run, "QUOTA_EXCEEDED")
                    return None
            item.attempts += 1
            item.lease_token = str(uuid4())
            item.lease_until = now + timedelta(seconds=LEASE_SECONDS)
            return item.ticket, item.lease_token

    def _settle(self, run_id, lease, workflow_id):
        with self.service._write() as session:
            item = session.get(AnalysisDispatch, run_id)
            if item is None or item.lease_token != lease:
                return
            item.lease_token, item.lease_until = None, None
            if workflow_id:
                item.workflow_id, item.last_error_code = workflow_id, None
                session.execute(
                    update(AnalysisRun)
                    .where(AnalysisRun.id == run_id)
                    .values(dispatch_state="accepted")
                )
            else:
                item.last_error_code = "DISPATCH_FAILED"
                item.next_attempt_at = utcnow() + timedelta(seconds=60 * 2 ** (item.attempts - 1))
                if item.attempts >= MAX_START_ATTEMPTS:
                    run = session.get(AnalysisRun, run_id)
                    if run:
                        fail_queued(session, run, "DISPATCH_FAILED")

    async def publish_owned(self, principal, run_id):
        await asyncio.to_thread(self.service.run, principal, run_id)
        await self.publish(run_id)
        return await asyncio.to_thread(self.service.run, principal, run_id)

    async def publish(self, run_id):
        claim = await asyncio.to_thread(self._claim, run_id)
        if claim is None:
            return
        ticket, lease = claim
        workflow_id = None
        cancelled = False
        try:
            workflow_id = await asyncio.wait_for(
                self.delivery.analysis(run_id, ticket), PUBLISH_SECONDS
            )
            if not isinstance(workflow_id, str) or not WORKFLOW_ID.fullmatch(workflow_id):
                workflow_id = None
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            # Provider errors/URLs/credentials never enter the product or queue event payload.
            pass
        await asyncio.to_thread(self._settle, run_id, lease, workflow_id)
        if cancelled:
            raise asyncio.CancelledError

    def _schedule_claim(self):
        with self.service._write() as session:
            day = utcnow().strftime("%Y-%m-%d")
            item = session.get(DispatchSchedule, day)
            if item is None:
                item = DispatchSchedule(day=day, attempts=0)
                session.add(item)
            if (
                item.workflow_id
                or item.attempts >= 2
                or item.lease_until
                and item.lease_until.replace(tzinfo=UTC) > utcnow()
            ):
                return None
            item.attempts += 1
            item.lease_token = str(uuid4())
            item.lease_until = utcnow() + timedelta(seconds=LEASE_SECONDS)
            return day, item.lease_token

    def _schedule_settle(self, day, lease, workflow_id):
        with self.service._write() as session:
            item = session.get(DispatchSchedule, day)
            if item and item.lease_token == lease:
                item.workflow_id = workflow_id
                item.lease_token, item.lease_until = None, None

    async def ensure_reconciler(self):
        claim = await asyncio.to_thread(self._schedule_claim)
        if claim is None:
            return
        day, lease = claim
        workflow_id = None
        cancelled = False
        try:
            workflow_id = await asyncio.wait_for(self.delivery.reconcile(), PUBLISH_SECONDS)
            if not isinstance(workflow_id, str) or not WORKFLOW_ID.fullmatch(workflow_id):
                workflow_id = None
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            pass
        await asyncio.to_thread(self._schedule_settle, day, lease, workflow_id)
        if cancelled:
            raise asyncio.CancelledError

    def _due(self, limit):
        self.service.expire_deadlines(limit=100)
        from ringsentinel.platform.upload_transport import UploadTransport

        UploadTransport(self.service).expire(limit=100)
        with self.service.database.session() as session:
            return [
                (item.run_id, item.workflow_id)
                for item in session.scalars(
                    select(AnalysisDispatch)
                    .join(AnalysisRun)
                    .where(
                        AnalysisRun.status == Status.QUEUED,
                        AnalysisDispatch.next_attempt_at <= utcnow(),
                    )
                    .order_by(AnalysisDispatch.next_attempt_at, AnalysisDispatch.run_id)
                    .limit(limit)
                )
            ]

    def _reset_failed_delivery(self, run_id, workflow_id):
        with self.service._write() as session:
            item = session.get(AnalysisDispatch, run_id)
            run = session.get(AnalysisRun, run_id)
            if item and run and run.status == Status.QUEUED and item.workflow_id == workflow_id:
                item.workflow_id = None
                item.next_attempt_at = utcnow()
                run.dispatch_state = "pending"

    def _defer_check(self, run_id, workflow_id):
        # Checking an accepted workflow must not starve later pending deliveries.
        with self.service._write() as session:
            item = session.get(AnalysisDispatch, run_id)
            if item and item.workflow_id == workflow_id:
                item.next_attempt_at = utcnow() + timedelta(seconds=120)

    async def reconcile(self, limit=10):
        if not 1 <= limit <= 10:
            raise ValueError("Invalid dispatch batch")
        candidates = await asyncio.to_thread(self._due, limit)
        for run_id, workflow_id in candidates:
            if workflow_id:
                await asyncio.to_thread(self._defer_check, run_id, workflow_id)
                try:
                    status = await asyncio.wait_for(self.delivery.status(workflow_id), 3)
                except Exception:
                    continue
                if status not in {"failed", "cancelled", "completed"}:
                    continue
                await asyncio.to_thread(self._reset_failed_delivery, run_id, workflow_id)
            await self.publish(run_id)
        return len(candidates)


def execute_dispatch(service, run_id, ticket):
    """Only the trusted SDK step calls this; resolve ownership from committed intent."""
    if service.settings.background_dispatch != "vercel_workflow":
        return "disabled"
    with service._write() as session:
        item = session.get(AnalysisDispatch, run_id)
        run = session.get(AnalysisRun, run_id)
        if item is None or run is None or item.ticket != ticket:
            return "deleted"
        if run.status == Status.QUEUED and run.version_metadata.get("model_artifact_sha256") != (
            service.settings.model_artifact_sha256 or "runtime-trained"
        ):
            fail_queued(session, run, "MODEL_VERSION_UNAVAILABLE")
            return "failed"
        owner = session.scalar(
            select(Investigation.owner_id).where(Investigation.id == run.investigation_id)
        )
    if owner is None:
        return "deleted"
    from ringsentinel.platform.jobs import RequestJobExecutor

    return RequestJobExecutor(service).execute_owned(Principal(owner), run_id).status.value


def exhaust_dispatch(service, run_id, ticket):
    if service.settings.background_dispatch != "vercel_workflow":
        return "disabled"
    with service._write() as session:
        item = session.get(AnalysisDispatch, run_id)
        run = session.get(AnalysisRun, run_id)
        if item is None or run is None or item.ticket != ticket:
            return "deleted"
        fail_queued(session, run, "CAPACITY_TIMEOUT")
        return run.status.value
