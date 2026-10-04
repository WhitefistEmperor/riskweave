"""Versioned investigation APIs and owner-scoped execution dispatch."""

import asyncio
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
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
    InvestigationDeleteRequest,
    InvestigationDeleteResponse,
    InvestigationPage,
    InvestigationResponse,
    InvestigatorRequest,
    InvestigatorResponse,
    ReadinessResponse,
    ResultChunkResponse,
    ResultManifestResponse,
    ResultsResponse,
    ReviewRequest,
    ReviewResponse,
    RunCreate,
    RunResponse,
    SessionResponse,
    UploadBegin,
    UploadCancelResponse,
    UploadProgress,
)
from ringsentinel.api.security import current_principal
from ringsentinel.investigation.investigator import InvestigatorService
from ringsentinel.platform.deletion import DeletionService
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import (
    AnalysisDispatch,
    CandidateReview,
    DispatchBudget,
    DispatchSchedule,
    Investigation,
    ResultFragment,
    ReviewAudit,
    Status,
    StorageDeletion,
)
from ringsentinel.platform.result_transport import ResultTransport
from ringsentinel.platform.reviews import ReviewService
from ringsentinel.platform.service import InvestigationService, Principal
from ringsentinel.platform.upload_transport import CHUNK_BYTES, UploadTransport

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
            if (
                session.scalar(text("SELECT version_num FROM alembic_version"))
                != service.database.revision
            ):
                return False
            session.execute(select(Investigation.id).limit(1))
            session.execute(select(CandidateReview.candidate_id).limit(1))
            session.execute(select(ResultFragment.run_id).limit(1))
            session.execute(select(AnalysisRun.candidate_count).limit(1))
            session.execute(select(ReviewAudit.id).limit(1))
            session.execute(select(StorageDeletion.key).limit(1))
            if service.settings.background_dispatch == "vercel_workflow":
                session.execute(select(AnalysisDispatch.run_id).limit(1))
                session.execute(select(DispatchBudget.month).limit(1))
                session.execute(select(DispatchSchedule.day).limit(1))
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
    if service.settings.jobs_enabled and service.settings.execution_mode == "local":
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


@router.get("/investigations/page", response_model=InvestigationPage)
def investigation_page(
    principal: CurrentPrincipal,
    service: Service,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    search: Annotated[str, Query(max_length=120)] = "",
    status: Status | None = None,
):
    return service.page(principal, offset=offset, limit=limit, search=search, status=status)


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
def investigation(investigation_id: str, principal: CurrentPrincipal, service: Service):
    return service.get(principal, investigation_id)


@router.delete("/investigations/{investigation_id}", response_model=InvestigationDeleteResponse)
def delete_investigation(
    investigation_id: str,
    body: InvestigationDeleteRequest,
    principal: CurrentPrincipal,
    service: Service,
):
    return DeletionService(service).remove(
        principal, investigation_id, body.confirm_name, body.expected_updated_at
    )


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


@router.get("/investigations/{investigation_id}/uploads", response_model=list[UploadProgress])
def pending_uploads(investigation_id: str, principal: CurrentPrincipal, service: Service):
    return UploadTransport(service).pending(principal, investigation_id)


@router.post("/investigations/{investigation_id}/uploads", response_model=UploadProgress)
def begin_upload(
    investigation_id: str,
    body: UploadBegin,
    principal: CurrentPrincipal,
    service: Service,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=80, pattern=r"^[\w-]+$")],
):
    return UploadTransport(service).begin(
        principal,
        investigation_id,
        name=body.name,
        size_bytes=body.size_bytes,
        checksum=body.checksum,
        key=idempotency_key,
    )


@router.put(
    "/investigations/{investigation_id}/uploads/{upload_id}/parts/{index}",
    response_model=UploadProgress,
)
async def receive_upload_part(
    investigation_id: str,
    upload_id: str,
    index: int,
    request: Request,
    principal: CurrentPrincipal,
    service: Service,
    x_chunk_sha256: Annotated[str, Header(pattern=r"^[a-f0-9]{64}$")],
):
    transport = UploadTransport(service)
    transport._supported()
    # Authorization precedes reading bytes; content length is only an early hint.
    await run_in_threadpool(service.get, principal, investigation_id)
    length = request.headers.get("content-length")
    if length and (not length.isdecimal() or int(length) > CHUNK_BYTES):
        raise ProductError("UPLOAD_TOO_LARGE")
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > CHUNK_BYTES:
            raise ProductError("UPLOAD_TOO_LARGE")
        payload.extend(chunk)
    return await run_in_threadpool(
        transport.receive,
        principal,
        investigation_id,
        upload_id,
        index,
        bytes(payload),
        x_chunk_sha256,
    )


@router.post(
    "/investigations/{investigation_id}/uploads/{upload_id}/complete",
    response_model=ArtifactResponse,
)
def complete_upload(
    investigation_id: str, upload_id: str, principal: CurrentPrincipal, service: Service
):
    return UploadTransport(service).complete(principal, investigation_id, upload_id)


@router.delete(
    "/investigations/{investigation_id}/uploads/{upload_id}",
    response_model=UploadCancelResponse,
)
def cancel_upload(
    investigation_id: str, upload_id: str, principal: CurrentPrincipal, service: Service
):
    return UploadTransport(service).cancel(principal, investigation_id, upload_id)


@router.get("/investigations/{investigation_id}/runs", response_model=list[RunResponse])
def runs(investigation_id: str, principal: CurrentPrincipal, service: Service):
    return service.runs(principal, investigation_id)


@router.post("/investigations/{investigation_id}/runs", response_model=RunResponse, status_code=202)
async def start_run(
    investigation_id: str,
    body: RunCreate,
    principal: CurrentPrincipal,
    service: Service,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=80, pattern=r"^[\w-]+$")],
):
    run = await run_in_threadpool(
        service.start, principal, investigation_id, body.artifact_id, idempotency_key
    )
    if request.app.state.dispatcher is not None:
        # Queue acceptance completes before the HTTP reply; inference runs in
        # the durable SDK step. An interrupted publish retains its SQL intent.
        run = await request.app.state.dispatcher.publish_owned(principal, run.id)
        await request.app.state.dispatcher.ensure_reconciler()
    return run


@router.get("/runs/{run_id}", response_model=RunResponse)
def run(run_id: str, principal: CurrentPrincipal, service: Service):
    return service.run(principal, run_id)


@router.post("/runs/{run_id}/execute", response_model=RunResponse)
async def execute_run(run_id: str, request: Request, principal: CurrentPrincipal, service: Service):
    saved = await run_in_threadpool(service.run, principal, run_id)
    if service.settings.execution_mode != "request":
        raise ProductError("CONFLICT")
    if (
        request.app.state.dispatcher is not None
        and saved.configuration_snapshot.get("background_dispatch") == "vercel_workflow"
    ):
        return await request.app.state.dispatcher.publish_owned(principal, run_id)
    return await run_in_threadpool(request.app.state.executor.execute_owned, principal, run_id)


@router.get("/operations/reconcile-delivery")
async def reconcile_delivery(request: Request, service: Service):
    secret = service.settings.dispatch_cron_secret.get_secret_value()
    supplied = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(
        supplied.encode("utf-8"), ("Bearer " + secret).encode("utf-8")
    ):
        raise ProductError("UNAUTHORIZED")
    if request.app.state.dispatcher is None:
        raise ProductError("NOT_READY")
    await request.app.state.dispatcher.ensure_reconciler()
    # A bounded immediate pass also repairs a failed reconciler registration.
    async with asyncio.timeout(150):
        count = await request.app.state.dispatcher.reconcile()
    return {"status": "checked", "batch_size": count}


@router.get("/runs/{run_id}/results", response_model=ResultsResponse)
def results(run_id: str, principal: CurrentPrincipal, service: Service):
    return service.result(principal, run_id, max_bytes=2_000_000)


@router.get("/runs/{run_id}/results/manifest", response_model=ResultManifestResponse)
def result_manifest(run_id: str, principal: CurrentPrincipal, service: Service):
    return ResultTransport(service).manifest(principal, run_id)


@router.get("/runs/{run_id}/results/chunks/{index}", response_model=ResultChunkResponse)
def result_chunk(run_id: str, index: int, principal: CurrentPrincipal, service: Service):
    return ResultTransport(service).chunk(principal, run_id, index)


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


@router.get("/runs/{run_id}/rings/{candidate_id}/review", response_model=ReviewResponse)
def review(run_id: str, candidate_id: str, principal: CurrentPrincipal, service: Service):
    return ReviewService(service).get(principal, run_id, candidate_id)


@router.post("/runs/{run_id}/rings/{candidate_id}/review", response_model=ReviewResponse)
def save_review(
    run_id: str,
    candidate_id: str,
    body: ReviewRequest,
    principal: CurrentPrincipal,
    service: Service,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=80, pattern=r"^[\w-]+$")],
):
    return ReviewService(service).save(
        principal,
        run_id,
        candidate_id,
        body.disposition,
        body.note,
        body.expected_version,
        idempotency_key,
    )


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
