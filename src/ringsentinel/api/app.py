"""FastAPI routes for the local RingSentinel analyst application."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from ringsentinel import __version__
from ringsentinel.api.observability import install_observability
from ringsentinel.api.platform_api import dependencies_ready
from ringsentinel.api.platform_api import router as platform_router
from ringsentinel.api.runtime import get_demo_runtime
from ringsentinel.investigation.investigator import InvestigatorService
from ringsentinel.platform.database import Database
from ringsentinel.platform.database_storage import storage_for
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.jobs import LocalJobExecutor, RequestJobExecutor
from ringsentinel.platform.service import InvestigationService
from ringsentinel.platform.settings import Settings


class RuntimeProvider(Protocol):
    def health(self) -> dict[str, Any]: ...
    def overview(self) -> dict[str, Any]: ...
    def benchmark(self) -> dict[str, Any]: ...
    def list_candidates(self) -> list[dict[str, Any]]: ...
    def candidate(self, candidate_id: str) -> dict[str, Any]: ...
    def candidate_graph(self, candidate_id: str) -> dict[str, Any]: ...
    def candidate_timeline(self, candidate_id: str) -> dict[str, Any]: ...
    def candidate_evidence(self, candidate_id: str) -> dict[str, Any]: ...
    def simulation(self) -> dict[str, Any]: ...
    def hard_negatives(self) -> list[dict[str, Any]]: ...
    def snapshot(self, event_count: int | None, candidate_id: str | None) -> dict[str, Any]: ...
    def snapshot_view(self, event_count: int | None = None) -> Any: ...


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=1000)
    event_count: int | None = Field(default=None, ge=1)


def create_app(
    runtime_factory: Callable[[], RuntimeProvider] = get_demo_runtime,
    *,
    settings: Settings | None = None,
    workflow_delivery=None,
) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_url.get_secret_value())
    platform = InvestigationService(database, storage_for(database, settings), settings)
    executor = (RequestJobExecutor if settings.execution_mode == "request" else LocalJobExecutor)(
        platform
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # Also configure direct uvicorn/Docker startup, not only the console entrypoint.
        logging.basicConfig(level=settings.log_level, format="%(message)s")
        logging.getLogger("ringsentinel.operations").info(
            json.dumps(
                {
                    "event": "startup",
                    "environment": settings.environment,
                    "authentication": settings.auth_mode,
                    "database": database.engine.dialect.name,
                    "jobs_enabled": settings.jobs_enabled,
                    "worker_topology": settings.execution_mode,
                    "storage_backend": settings.storage_backend,
                    "llm_provider": settings.llm_provider,
                    "upload_limit_bytes": settings.upload_limit_bytes,
                    "storage_limit_bytes": settings.storage_limit_bytes,
                    "build_commit": settings.build_commit,
                },
                sort_keys=True,
            )
        )
        # Migrations are an explicit operator step; startup never creates/changes schema.
        if (
            settings.execution_mode == "local"
            and settings.jobs_enabled
            and dependencies_ready(platform)
        ):
            executor.start()
        try:
            yield
        finally:
            executor.stop()
            database.engine.dispose()

    application = FastAPI(
        title="RiskWeave API",
        description="Persisted investigations with a separate synthetic demonstration surface.",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    application.state.settings = settings
    application.state.platform = platform
    application.state.executor = executor
    application.state.dispatcher = None
    if settings.background_dispatch == "vercel_workflow":
        if settings.environment == "production" and (
            not os.getenv("VERCEL_DEPLOYMENT_ID")
            or os.getenv("WORKFLOW_TARGET_WORLD", "vercel") != "vercel"
        ):
            raise ValueError("Production workflows require the Vercel managed runtime")
        from ringsentinel.platform.dispatch import DeliveryCoordinator

        if workflow_delivery is None:
            from ringsentinel.platform.workflows import VercelWorkflowDelivery

            workflow_delivery = VercelWorkflowDelivery()
        application.state.dispatcher = DeliveryCoordinator(platform, workflow_delivery)
    if settings.auth_mode == "jwt":
        from ringsentinel.api.authentication import TokenVerifier

        application.state.token_verifier = TokenVerifier(settings)
    from ringsentinel.platform.providers import provider_from_settings

    application.state.summary_provider = provider_from_settings(settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Development-User",
            "X-Filename",
            "Idempotency-Key",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )
    install_observability(application)
    application.include_router(platform_router)

    def demo_available():
        if not settings.demo_enabled:
            raise ProductError("NOT_FOUND")

    demo = APIRouter(dependencies=[Depends(demo_available)])

    def call_candidate(method: Callable[[str], Any], candidate_id: str) -> Any:
        try:
            return method(candidate_id)
        except (KeyError, StopIteration) as error:
            raise HTTPException(status_code=404, detail="Candidate ring not found") from error

    @demo.get("/api/health")
    def health() -> dict[str, Any]:
        return runtime_factory().health()

    @demo.get("/api/overview")
    def overview() -> dict[str, Any]:
        return runtime_factory().overview()

    @demo.get("/api/benchmark")
    def benchmark() -> dict[str, Any]:
        return runtime_factory().benchmark()

    @demo.get("/api/candidates")
    def candidates() -> list[dict[str, Any]]:
        return runtime_factory().list_candidates()

    @demo.get("/api/candidates/{candidate_id}")
    def candidate(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate, candidate_id)

    @demo.get("/api/candidates/{candidate_id}/graph")
    def candidate_graph(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate_graph, candidate_id)

    @demo.get("/api/candidates/{candidate_id}/timeline")
    def candidate_timeline(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate_timeline, candidate_id)

    @demo.get("/api/candidates/{candidate_id}/evidence")
    def candidate_evidence(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate_evidence, candidate_id)

    @demo.get("/api/simulation")
    def simulation() -> dict[str, Any]:
        return runtime_factory().simulation()

    @demo.get("/api/hard-negatives")
    def hard_negatives() -> list[dict[str, Any]]:
        return runtime_factory().hard_negatives()

    @demo.get("/api/snapshot")
    def snapshot(
        event_count: int | None = Query(default=None, ge=1),
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            return runtime_factory().snapshot(event_count, candidate_id)
        except (KeyError, StopIteration) as error:
            raise HTTPException(
                status_code=404, detail="Candidate unavailable in this snapshot"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @demo.post("/api/investigate")
    def investigate(body: InvestigationRequest) -> dict[str, Any]:
        try:
            view = runtime_factory().snapshot_view(body.event_count)
            return InvestigatorService(view.evidence, application.state.summary_provider).answer(
                body.candidate_id, body.question
            )
        except (KeyError, StopIteration) as error:
            raise HTTPException(
                status_code=404, detail="Candidate unavailable in this snapshot"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    application.include_router(demo)
    return application


app = create_app()


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    uvicorn.run(
        "ringsentinel.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,
        access_log=False,
        timeout_graceful_shutdown=15,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
