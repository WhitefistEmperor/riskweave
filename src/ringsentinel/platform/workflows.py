"""Vercel workflow orchestration; inputs contain opaque IDs, never payment data/tokens."""

import asyncio

from vercel import workflow

wf = workflow.Workflows(namespace="riskweave")


def _service():
    # Each step invocation gets fresh durable dependencies. No database/client in
    # the deterministic workflow sandbox or in serialized arguments/results.
    # Generated workflow functions may load the registry without importing app.py.
    # They must use the identical release-owned artifact, never runtime retraining.
    import os
    from pathlib import Path

    from ringsentinel.platform.database import Database
    from ringsentinel.platform.database_storage import storage_for
    from ringsentinel.platform.service import InvestigationService
    from ringsentinel.platform.settings import Settings

    if os.getenv("VERCEL_DEPLOYMENT_ID") and os.getenv("RINGSENTINEL_ENVIRONMENT") == "production":
        from ringsentinel.platform.vercel_entry import configure_bundle

        configure_bundle(Path.cwd())

    settings = Settings()
    database = Database(settings.database_url.get_secret_value())
    return InvestigationService(database, storage_for(database, settings), settings)


@wf.step(max_retries=1)
async def attempt_analysis(run_id: str, ticket: str) -> str:
    from ringsentinel.platform.dispatch import execute_dispatch

    service = None
    try:
        service = _service()
        return await asyncio.to_thread(execute_dispatch, service, run_id, ticket)
    except Exception:
        raise workflow.RetryableError("Analysis service unavailable", retry_after="30s") from None
    finally:
        if service is not None:
            service.database.engine.dispose()


@wf.step(max_retries=1)
async def capacity_exhausted(run_id: str, ticket: str) -> str:
    from ringsentinel.platform.dispatch import exhaust_dispatch

    service = None
    try:
        service = _service()
        return await asyncio.to_thread(exhaust_dispatch, service, run_id, ticket)
    except Exception:
        raise workflow.RetryableError("Analysis recovery unavailable", retry_after="30s") from None
    finally:
        if service is not None:
            service.database.engine.dispose()


@wf.workflow
async def analyze_saved_run(run_id: str, ticket: str) -> str:
    for attempt in range(40):
        status = await attempt_analysis(run_id, ticket)
        if status in {"completed", "failed", "deleted", "disabled"}:
            return status
        if attempt < 39:
            await workflow.sleep("120s")
    return await capacity_exhausted(run_id, ticket)


@wf.step(max_retries=1)
async def reconcile_deliveries() -> int:
    from ringsentinel.platform.dispatch import DeliveryCoordinator

    service = None
    try:
        service = _service()
        if service.settings.background_dispatch != "vercel_workflow":
            return 0
        return await DeliveryCoordinator(service, VercelWorkflowDelivery()).reconcile()
    except Exception:
        raise workflow.RetryableError("Delivery recovery unavailable", retry_after="30s") from None
    finally:
        if service is not None:
            service.database.engine.dispose()


@wf.workflow
async def delivery_reconciler() -> None:
    # One per UTC day, with overlap for Hobby cron's scheduling window. All
    # admission still uses database leases; duplicate reconcilers cannot claim
    # an analysis twice. Fixed iterations bound event growth/replay cost.
    for cycle in range(27):
        await reconcile_deliveries()
        if cycle < 26:
            await workflow.sleep("1h")


class VercelWorkflowDelivery:
    async def analysis(self, run_id: str, ticket: str) -> str:
        run = await workflow.start(analyze_saved_run, run_id=run_id, ticket=ticket)
        return run.run_id

    async def reconcile(self) -> str:
        run = await workflow.start(delivery_reconciler)
        return run.run_id

    async def status(self, workflow_id: str) -> str:
        return await workflow.Run(workflow_id).status()
