"""FastAPI app factory: CORS, request ids + timing log, body limit, ErrorResponse handlers, routers."""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api import routes_ask, routes_misc, routes_scan
from backend.app.body_limit import BodyLimit
from backend.app.config import get_settings
from backend.app.errors import ApiError
from backend.app.logging_setup import configure_logging, current_request, logger, start_request
from backend.app.pipeline import ocr
from shared.contract import ErrorResponse

REQUEST_ID_HEADER = "X-Request-ID"
_STATUS_CODES = {400: "VALIDATION", 404: "NOT_FOUND", 405: "VALIDATION", 413: "BAD_IMAGE", 429: "RATE_LIMITED"}


def error_response(status: int, error_code: str, message: str, retry_after_s: int | None = None) -> JSONResponse:
    body = ErrorResponse(error_code=error_code, message=message, retry_after_s=retry_after_s)
    headers = {"Retry-After": str(retry_after_s)} if retry_after_s is not None else None
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


async def handle_api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(exc.status, exc.error_code, exc.message, exc.retry_after_s)


async def handle_validation(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    problems = [
        f"{'.'.join(str(p) for p in err.get('loc', ()) if p != 'body') or 'body'}: {err.get('msg', 'invalid')}"
        for err in exc.errors()[:5]
    ]
    return error_response(400, "VALIDATION", "Invalid request. " + "; ".join(problems))


async def handle_http(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return error_response(exc.status_code, _STATUS_CODES.get(exc.status_code, "INTERNAL"), str(exc.detail))


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    log = current_request()
    logger.error("unhandled error", exc_info=exc, extra={"fields": {
        "request_id": log.request_id if log else None, "route": request.url.path,
    }})
    return error_response(500, "INTERNAL", "Something went wrong on our side. Please try again.")


async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    log = start_request(request_id)
    started = time.perf_counter()
    try:
        response: Response = await call_next(request)
    except Exception as exc:  # last resort; route errors normally reach the handlers above
        response = await handle_unexpected(request, exc)
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info("request", extra={"fields": {
        "request_id": request_id,
        "method": request.method,
        "route": request.url.path,
        "status": response.status_code,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "stages": log.stages,
        **log.extra,
    }})
    return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    await run_in_threadpool(ocr.get_engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="LabelLens API", version="0.1.0", lifespan=lifespan)
    # Added first = innermost: oversized bodies still get a request id, a log line and CORS headers.
    app.add_middleware(BodyLimit, scan_limit=lambda: get_settings().max_scan_body_bytes,
                       respond=lambda e: error_response(e.status, e.error_code, e.message))
    app.middleware("http")(request_context)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation)
    app.add_exception_handler(StarletteHTTPException, handle_http)
    app.add_exception_handler(Exception, handle_unexpected)
    for router in (routes_scan.router, routes_ask.router, routes_misc.router):
        app.include_router(router)
    logging.getLogger("uvicorn.access").disabled = True
    return app


app = create_app()
