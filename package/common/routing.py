"""Main route registration for every microservice."""
from __future__ import annotations

from typing import Iterable

from fastapi import APIRouter, FastAPI


def register_routes(
    app: FastAPI,
    routers: Iterable[APIRouter],
    *,
    api_prefix: str = "/api/v1",
) -> None:
    """Mount all domain routers under the service API prefix.

    Call this from ``app.main.create_app`` — one clear entry for HTTP paths.
    """
    for router in routers:
        app.include_router(router, prefix=api_prefix)
