"""Safe HTTP errors and structured, payload-free request correlation."""

import json
import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from ringsentinel.platform.errors import ProductError

logger = logging.getLogger("ringsentinel.http")


def error_response(request: Request, error: ProductError) -> JSONResponse:
    request.state.failure_category = error.code
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "request_id": request.state.request_id,
            }
        },
        headers={"X-Request-ID": request.state.request_id},
    )


def install_observability(application: FastAPI) -> None:
    @application.exception_handler(ProductError)
    async def product_error(request: Request, error: ProductError):
        return error_response(request, error)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return error_response(request, ProductError("VALIDATION_ERROR"))

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        category = {
            400: "INVALID_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            413: "UPLOAD_TOO_LARGE",
            422: "VALIDATION_ERROR",
        }.get(error.status_code, "INTERNAL_ERROR")
        return error_response(request, ProductError(category))

    @application.middleware("http")
    async def correlated_request(request: Request, call_next):
        request.state.request_id = str(uuid4())
        request.state.failure_category = None
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Neither exception strings nor raw request paths are safe logging fields.
            response = error_response(request, ProductError("INTERNAL_ERROR"))
            origin = request.headers.get("origin")
            if origin and origin in request.app.state.settings.frontend_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                response.headers["Vary"] = "Origin"
        # CORS rejects preflight before reaching route exception handlers.
        if response.status_code >= 400 and request.state.failure_category is None:
            original = response
            code = "INVALID_REQUEST" if response.status_code == 400 else "INTERNAL_ERROR"
            response = error_response(request, ProductError(code))
            for key, value in original.headers.items():
                if key.lower().startswith("access-control-") or key.lower() == "vary":
                    response.headers[key] = value
        response.headers["X-Request-ID"] = request.state.request_id
        fields = {
            "event": "http_request",
            "request_id": request.state.request_id,
            "method": request.method,
            "route": getattr(request.scope.get("route"), "path", "unmatched"),
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "failure_category": request.state.failure_category,
        }
        for name in ("investigation_id", "run_id"):
            value = request.path_params.get(name)
            if value and re.fullmatch(r"[a-f0-9-]{36}", value):
                fields[name] = value
        logger.info(json.dumps(fields, sort_keys=True))
        return response
