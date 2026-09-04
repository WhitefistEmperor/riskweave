"""FastAPI routes for the local RingSentinel analyst application."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ringsentinel.api.runtime import get_demo_runtime


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


def create_app(
    runtime_factory: Callable[[], RuntimeProvider] = get_demo_runtime,
) -> FastAPI:
    application = FastAPI(
        title="RingSentinel API",
        description="Local evidence and simulation API for coordinated payment-abuse analysis.",
        version="0.4.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def call_candidate(method: Callable[[str], Any], candidate_id: str) -> Any:
        try:
            return method(candidate_id)
        except (KeyError, StopIteration) as error:
            raise HTTPException(status_code=404, detail="Candidate ring not found") from error

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        return runtime_factory().health()

    @application.get("/api/overview")
    def overview() -> dict[str, Any]:
        return runtime_factory().overview()

    @application.get("/api/benchmark")
    def benchmark() -> dict[str, Any]:
        return runtime_factory().benchmark()

    @application.get("/api/candidates")
    def candidates() -> list[dict[str, Any]]:
        return runtime_factory().list_candidates()

    @application.get("/api/candidates/{candidate_id}")
    def candidate(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate, candidate_id)

    @application.get("/api/candidates/{candidate_id}/graph")
    def candidate_graph(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate_graph, candidate_id)

    @application.get("/api/candidates/{candidate_id}/timeline")
    def candidate_timeline(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate_timeline, candidate_id)

    @application.get("/api/candidates/{candidate_id}/evidence")
    def candidate_evidence(
        candidate_id: str,
    ) -> dict[str, Any]:
        return call_candidate(runtime_factory().candidate_evidence, candidate_id)

    @application.get("/api/simulation")
    def simulation() -> dict[str, Any]:
        return runtime_factory().simulation()

    @application.get("/api/hard-negatives")
    def hard_negatives() -> list[dict[str, Any]]:
        return runtime_factory().hard_negatives()

    @application.get("/api/snapshot")
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

    return application


app = create_app()


def main() -> None:
    uvicorn.run("ringsentinel.api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
