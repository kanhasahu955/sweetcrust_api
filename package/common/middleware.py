"""Shared FastAPI middlewares — CORS, request id/timing, exception handlers."""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from package.common.errors import register_exception_handlers
from package.common.settings import get_settings

log = logging.getLogger("package.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = rid
        response.headers["X-Response-Time"] = f"{ms:.1f}ms"
        if get_settings().request_log:
            log.info(
                "%s %s → %s %.1fms id=%s",
                request.method,
                request.url.path,
                response.status_code,
                ms,
                rid[:8],
            )
        return response


def setup_middleware(app: FastAPI) -> None:
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-Response-Time"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
