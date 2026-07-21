"""Unified API + database error handling for all FastAPI services."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from package.common.schemas import fail

logger = logging.getLogger("package.errors")


class AppError(Exception):
    """Raise inside services — mapped to a consistent JSON envelope."""

    def __init__(
        self,
        detail: Any,
        *,
        status_code: int = 400,
        code: str = "app_error",
    ):
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(str(detail))


class NotFoundError(AppError):
    def __init__(self, detail: Any = "Not found", *, code: str = "not_found"):
        super().__init__(detail, status_code=404, code=code)


class UnauthorizedError(AppError):
    def __init__(self, detail: Any = "Unauthorized", *, code: str = "unauthorized"):
        super().__init__(detail, status_code=401, code=code)


class ForbiddenError(AppError):
    def __init__(self, detail: Any = "Forbidden", *, code: str = "forbidden"):
        super().__init__(detail, status_code=403, code=code)


class ConflictError(AppError):
    def __init__(self, detail: Any = "Conflict", *, code: str = "conflict"):
        super().__init__(detail, status_code=409, code=code)


class ValidationAppError(AppError):
    def __init__(self, detail: Any = "Validation failed", *, code: str = "validation_error"):
        super().__init__(detail, status_code=422, code=code)


class DatabaseAppError(AppError):
    def __init__(self, detail: Any = "Database error", *, code: str = "database_error", status_code: int = 503):
        super().__init__(detail, status_code=status_code, code=code)


class RateLimitError(AppError):
    def __init__(self, detail: Any = "Too many requests", *, code: str = "rate_limited"):
        super().__init__(detail, status_code=429, code=code)


class ServiceUnavailableError(AppError):
    def __init__(self, detail: Any = "Service unavailable", *, code: str = "unavailable"):
        super().__init__(detail, status_code=503, code=code)


class BadRequestError(AppError):
    def __init__(self, detail: Any = "Bad request", *, code: str = "bad_request"):
        super().__init__(detail, status_code=400, code=code)


class BadGatewayError(AppError):
    def __init__(self, detail: Any = "Upstream failed", *, code: str = "bad_gateway"):
        super().__init__(detail, status_code=502, code=code)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid.uuid4())


def _map_db_error(exc: SQLAlchemyError) -> tuple[int, str, Any]:
    if isinstance(exc, IntegrityError):
        return 409, "integrity_error", "Database constraint violated"
    if isinstance(exc, OperationalError):
        return 503, "database_unavailable", "Database unavailable"
    return 500, "database_error", "Database error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        rid = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.detail, code=exc.code, request_id=rid),
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        rid = _request_id(request)
        code = {
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            429: "rate_limited",
            503: "unavailable",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.detail, code=code, request_id=rid),
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        rid = _request_id(request)
        return JSONResponse(
            status_code=422,
            content=fail(exc.errors(), code="validation_error", request_id=rid),
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError):
        rid = _request_id(request)
        status, code, detail = _map_db_error(exc)
        logger.exception("database error code=%s", code)
        return JSONResponse(
            status_code=status,
            content=fail(detail, code=code, request_id=rid),
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        rid = _request_id(request)
        logger.exception("unhandled error request_id=%s", rid)
        # Hide internals outside development
        from package.common.settings import get_settings

        detail: Any = str(exc) if get_settings().is_dev else "Internal server error"
        return JSONResponse(
            status_code=500,
            content=fail(detail, code="internal_error", request_id=rid),
            headers={"X-Request-Id": rid},
        )
