"""Shared settings, errors, schemas, auth guards, utils, middleware, lifecycle."""

from package.common.errors import (
    AppError,
    BadGatewayError,
    BadRequestError,
    ConflictError,
    DatabaseAppError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationAppError,
    register_exception_handlers,
)
from package.common.factory import create_service_app
from package.common.lifecycle import service_lifespan
from package.common.middleware import setup_middleware
from package.common.rate_limit import enforce_rate
from package.common.schemas import DataOut, ErrorBody, HealthOut, MessageOut, fail, ok
from package.common.settings import Settings, configure_settings, get_settings, reload_settings
from package.common.utils.datetime import day_bounds, days_ago, utc_now, utc_now_aware, utc_today

__all__ = [
    "Settings",
    "configure_settings",
    "get_settings",
    "reload_settings",
    "create_service_app",
    "setup_middleware",
    "service_lifespan",
    "register_exception_handlers",
    "enforce_rate",
    "AppError",
    "NotFoundError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "ValidationAppError",
    "DatabaseAppError",
    "RateLimitError",
    "ServiceUnavailableError",
    "BadRequestError",
    "BadGatewayError",
    "ErrorBody",
    "MessageOut",
    "DataOut",
    "HealthOut",
    "ok",
    "fail",
    "utc_now",
    "utc_now_aware",
    "utc_today",
    "day_bounds",
    "days_ago",
]
