"""Store Ops FastAPI app — async OOP."""
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
from package.database import init_db, ping_async_db, ping_db, pool_status
from package.logger import get_logger
from package.redis import redis_ping

logger = get_logger("store_ops")
boot_settings()

async def _startup() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("store_ops_service ready (async-oop)")

@asynccontextmanager
async def lifespan(app: FastAPI):
    boot_settings()
    async with service_lifespan(app, service="store_ops", version=get_settings().service_version, on_startup=_startup):
        yield

def create_app() -> FastAPI:
    boot_settings()
    app = create_service_app(
        title="SweetCrust Store Ops",
        version=get_settings().service_version,
        description="Admin dashboard + retailer BFF (async OOP)",
        lifespan=lifespan,
    )
    routes.mount(app)

    upload_root = Path(get_settings().upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads_static")

    @app.get("/health", response_model=HealthOut)
    async def health():
        db_ok = ping_db()
        try:
            async_ok = await ping_async_db()
        except Exception:
            async_ok = False
        try:
            redis_ok = bool(redis_ping())
        except Exception:
            redis_ok = False
        return HealthOut(
            service="store_ops",
            ok=db_ok,
            database=db_ok,
            redis=redis_ok,
            status="running" if db_ok else "degraded",
            details={"pool": pool_status(), "async_db": async_ok},
        )

    @app.post("/seed")
    def seed():
        init_db()
        logger.info("seed/schema ensure")
        return ok(message="schema ensured")

    return app

app = create_app()
