"""Admin + retailer BFF FastAPI app — package factory."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app import routes
from app.config import boot_settings, get_settings
from package.common.factory import create_service_app
from package.common.lifecycle import service_lifespan
from package.common.schemas import HealthOut, ok
from package.database import init_db, ping_db, pool_status
from package.logger import get_logger
from package.redis import redis_ping

logger = get_logger("admin")

boot_settings()


def _admin_startup() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("admin_service ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    boot_settings()
    async with service_lifespan(
        app,
        service="admin",
        version=get_settings().service_version,
        on_startup=_admin_startup,
    ):
        yield


def create_app() -> FastAPI:
    boot_settings()
    app = create_service_app(
        title="SweetCrust Admin",
        version=get_settings().service_version,
        description="Admin dashboard + temporary retailer BFF",
        lifespan=lifespan,
    )
    app.include_router(routes.admin_router, prefix="/api/v1")
    app.include_router(routes.retailer_router, prefix="/api/v1")
    app.include_router(routes.uploads_router, prefix="/api/v1")
    # also serve at /uploads for gateway root proxy
    app.include_router(routes.uploads_router)

    upload_root = Path(get_settings().upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads_static")

    @app.get("/health", response_model=HealthOut)
    def health():
        db_ok = ping_db()
        try:
            redis_ok = bool(redis_ping())
        except Exception:
            redis_ok = False
        return HealthOut(
            service="admin",
            ok=db_ok,
            database=db_ok,
            redis=redis_ok,
            status="running" if db_ok else "degraded",
            details={"pool": pool_status()},
        )

    @app.post("/seed")
    def seed():
        init_db()
        logger.info("seed/schema ensure")
        return ok(message="schema ensured")

    return app


app = create_app()
