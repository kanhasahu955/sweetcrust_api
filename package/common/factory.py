"""Shared FastAPI app factory — every microservice should use this."""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI

from package.common.middleware import setup_middleware
from package.common.settings import get_settings


def create_service_app(
    *,
    title: str,
    version: Optional[str] = None,
    description: str = "",
    lifespan: Optional[Callable[..., Any]] = None,
) -> FastAPI:
    """Create FastAPI app with package middleware + error handlers already wired."""
    settings = get_settings()
    app = FastAPI(
        title=title,
        version=version or settings.service_version,
        description=description,
        lifespan=lifespan,
    )
    setup_middleware(app)
    return app
