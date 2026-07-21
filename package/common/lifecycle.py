"""Shared FastAPI lifespan: logging → DB connect → boot banner → disconnect."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI

from package.common.settings import get_settings, reload_settings
from package.database import connect_db, disconnect_db, ping_db
from package.logger import get_logger, log_service_boot, setup_logging

log = get_logger("package.lifecycle")

StartupHook = Callable[[], Any] | Callable[[], Awaitable[Any]]


async def _maybe_await(fn: Optional[StartupHook]) -> None:
    if fn is None:
        return
    result = fn()
    if hasattr(result, "__await__"):
        await result  # type: ignore[misc]


@asynccontextmanager
async def service_lifespan(
    app: FastAPI,
    *,
    service: Optional[str] = None,
    version: Optional[str] = None,
    on_startup: Optional[StartupHook] = None,
    on_shutdown: Optional[StartupHook] = None,
    extra: Optional[Mapping[str, Any]] = None,
):
    """
    Use as FastAPI lifespan:

        @asynccontextmanager
        async def lifespan(app):
            async with service_lifespan(app, service="ai"):
                ... seed ...
                yield
    """
    settings = reload_settings()
    name = service or settings.service_name
    ver = version or settings.service_version

    setup_logging(
        settings.log_level,
        json_logs=settings.log_json,
        color=settings.log_color and not settings.log_json,
    )
    log.info("lifespan start · %s", name)

    connect_db()
    db_ok = ping_db()
    try:
        from package.database import connect_async_db, ping_async_db

        await connect_async_db()
        if not await ping_async_db():
            log.warning("async db ping failed — sync pool still available")
    except Exception as exc:
        log.warning("async db init skipped: %s", exc.__class__.__name__)

    redis_ok: Optional[bool] = None
    try:
        from package.redis import redis_ping

        redis_ok = bool(redis_ping()) if settings.redis_configured else False
    except Exception:
        redis_ok = False

    await _maybe_await(on_startup)

    log_service_boot(
        app,
        service=name,
        version=ver,
        db_ok=db_ok,
        redis_ok=redis_ok,
        extra=dict(extra or {}, async_db=True),
    )

    try:
        yield {"db_ok": db_ok, "redis_ok": redis_ok}
    finally:
        await _maybe_await(on_shutdown)
        try:
            from package.database import disconnect_async_db as _disc_async

            await _disc_async()
        except Exception:
            pass
        disconnect_db()
        log.info("lifespan stop · %s", name)
