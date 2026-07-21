"""Main route table for store_ops_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.admin import router as admin_router
from app.routes.retailer import router as retailer_router
from app.routes.uploads import router as uploads_router
from package.common.routing import register_routes

ROUTERS = (admin_router, retailer_router, uploads_router)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
    # also serve at /uploads for gateway root proxy
    app.include_router(uploads_router)
