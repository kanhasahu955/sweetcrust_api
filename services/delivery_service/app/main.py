"""SweetCrust Delivery FastAPI app — package factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401
from app import routes
from app.config import boot_settings, get_settings
from package.common.factory import create_service_app
from package.common.lifecycle import service_lifespan
from package.common.schemas import HealthOut
from package.database import init_db, ping_db, pool_status
from package.logger import get_logger
from package.redis import redis_ping

logger = get_logger("delivery")

boot_settings()


def _startup() -> None:
    init_db()
    logger.info("delivery_service ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    boot_settings()
    async with service_lifespan(
        app,
        service="delivery",
        version=get_settings().service_version,
        on_startup=_startup,
    ):
        yield


def create_app() -> FastAPI:
    boot_settings()
    app = create_service_app(
        title="SweetCrust Delivery",
        version=get_settings().service_version,
        description="Rider app + radius check",
        lifespan=lifespan,
    )
    app.include_router(routes.delivery_router, prefix="/api/v1")
    app.include_router(routes.customer_router, prefix="/api/v1")

    @app.get("/health", response_model=HealthOut)
    def health():
        db_ok = ping_db()
        try:
            redis_ok = bool(redis_ping())
        except Exception:
            redis_ok = False
        return HealthOut(
            service="delivery",
            ok=db_ok,
            database=db_ok,
            redis=redis_ok,
            status="running" if db_ok else "degraded",
            details={"pool": pool_status()},
        )

    return app


app = create_app()
