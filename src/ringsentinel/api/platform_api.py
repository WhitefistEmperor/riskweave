"""Versioned investigation APIs. No detector work occurs in request handlers."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select, text
from starlette.concurrency import run_in_threadpool

from ringsentinel import __version__
from ringsentinel.api.contracts import (
    ArtifactResponse,
    CandidateResponse,
    ErrorResponse,
    EvidenceResponse,
    HealthResponse,
    InvestigationCreate,
    InvestigationResponse,
    InvestigatorRequest,
    InvestigatorResponse,
    ReadinessResponse,
    ResultsResponse,
    RunCreate,
    RunResponse,
    SessionResponse,
)
from ringsentinel.api.security import current_principal
from ringsentinel.investigation.investigator import InvestigatorService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import Investigation
from ringsentinel.platform.service import InvestigationService, Principal

router = APIRouter(
    prefix="/api/v1",
    responses={
        code: {"model": ErrorResponse}
        for code in (400, 401, 403, 404, 405, 409, 413, 422, 429, 500, 503)
    },
)
CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def service_for(request: Request) -> InvestigationService:
    return request.app.state.platform


Service = Annotated[InvestigationService, Depends(service_for)]


def dependencies_ready(service: InvestigationService) -> bool:
    try:
        with service.database.session() as session:
            # Check the migration and actual domain table, not just socket connectivity.
            if session.scalar(text("SELECT version_num FROM alembic_version")) != "0001":
                return False
            session.execute(select(Investigation.id).limit(1))
        return service.storage.ready()
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse, tags=["operations"])
def health():
    return HealthResponse(application_version=__version__)


@router.get("/ready", response_model=ReadinessResponse, tags=["operations"])
def readiness(request: Request, service: Service):
    if not dependencies_ready(service):
        raise ProductError("NOT_READY")
    if service.settings.jobs_enabled:
        thread = request.app.state.executor.thread
        if thread is None or not thread.is_alive():
            raise ProductError("NOT_READY")
    return ReadinessResponse()


@router.get("/session", response_model=SessionResponse, tags=["session"])
def session(request: Request, principal: CurrentPrincipal):
    mode = request.app.state.settings.auth_mode
    return SessionResponse(
        user_id=principal.user_id, authentication_mode=mode, production_authentication=mode == "jwt"
    )


@router.get("/investigations", response_model=list[InvestigationResponse])
def investigations(principal: CurrentPrincipal, service: Service):
    return service.list(principal)


@router.post("/investigations", response_model=InvestigationResponse, status_code=201)
def create_investigation(body: InvestigationCreate, principal: CurrentPrincipal, service: Service):
    return service.create(principal, body.name)


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
def investigation(investigation_id: str, principal: CurrentPrincipal, service: Service):
    return service.get(principal, investigation_id)


@router.get("/investigations/{investigation_id}/artifacts", response_model=list[ArtifactResponse])
def artifacts(investigation_id: str, principal: CurrentPrincipal, service: Service):
    return service.artifacts(principal, investigation_id)


@router.post(
    "/investigations/{investigation_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"type": "object", "description": "DatasetBundle JSON"}
                }
            },
        }
    },
)
async def upload_artifact(
    investigation_id: str,
    request: Request,
    principal: CurrentPrincipal,
    service: Service,
    x_filename: Annotated[str, Header(max_length=200)] = "dataset.json",
):
    # Authorize before consuming untrusted upload data. Never trust Content-Length alone.
    await run_in_threadpool(service.get, principal, investigation_id)
    length = request.headers.get("content-length")
    if length:
        if not length.isdecimal():
            raise ProductError("VALIDATION_ERROR")
        if int(length) > service.settings.upload_limit_bytes:
            raise ProductError("UPLOAD_TOO_LARGE")
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise ProductError("INVALID_DATASET")
    if any(char in x_filename for char in ("/", "\\", ":")) or x_filename in {".", ".."}:
        raise ProductError("INVALID_DATASET")
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > service.settings.upload_limit_bytes:
            raise ProductError("UPLOAD_TOO_LARGE")
        payload.extend(chunk)
    return await run_in_threadpool(
        service.attach, principal, investigation_id, bytes(payload), x_filename, content_type
    )


@router.get("/investigations/{investigation_id}/runs", response_model=list[RunResponse])
def runs(investigation_id: str, principal: CurrentPrincipal, service: Service):
    return service.runs(principal, investigation_id)


@router.post("/investigations/{investigation_id}/runs", response_model=RunResponse, status_code=202)
def start_run(
    investigation_id: str,
    body: RunCreate,
    principal: CurrentPrincipal,
    service: Service,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=80, pattern=r"^[\w-]+$")],
):
    return service.start(principal, investigation_id, body.artifact_id, idempotency_key)


@router.get("/runs/{run_id}", response_model=RunResponse)
def run(run_id: str, principal: CurrentPrincipal, service: Service):
    return service.run(principal, run_id)


@router.get("/runs/{run_id}/results", response_model=ResultsResponse)
def results(run_id: str, principal: CurrentPrincipal, service: Service):
    return service.result(principal, run_id)


@router.get("/runs/{run_id}/rings", response_model=list[CandidateResponse])
def rings(run_id: str, principal: CurrentPrincipal, service: Service):
    return [ring["candidate"] for ring in service.result(principal, run_id)["rings"]]


def ring_for(result: dict, candidate_id: str) -> dict:
    for ring in result["rings"]:
        if ring["candidate"]["candidate_id"] == candidate_id:
            return ring
    raise ProductError("NOT_FOUND")


@router.get("/runs/{run_id}/rings/{candidate_id}", response_model=CandidateResponse)
def candidate(run_id: str, candidate_id: str, principal: CurrentPrincipal, service: Service):
    return ring_for(service.result(principal, run_id), candidate_id)["candidate"]


@router.get("/runs/{run_id}/rings/{candidate_id}/evidence", response_model=EvidenceResponse)
def evidence(run_id: str, candidate_id: str, principal: CurrentPrincipal, service: Service):
    return ring_for(service.result(principal, run_id), candidate_id)["queries"]


@router.post("/runs/{run_id}/rings/{candidate_id}/investigate", response_model=InvestigatorResponse)
def investigate(
    run_id: str,
    candidate_id: str,
    body: InvestigatorRequest,
    request: Request,
    principal: CurrentPrincipal,
    service: Service,
):
    from ringsentinel.platform.analysis import PersistedEvidence

    result = service.result(principal, run_id)
    ring_for(result, candidate_id)
    return InvestigatorService(
        PersistedEvidence(result), request.app.state.summary_provider
    ).answer(candidate_id, body.question)
