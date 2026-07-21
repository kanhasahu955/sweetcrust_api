"""Main route table for ai_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.api import admin_router, customer_router, retailer_router, root_router
from package.common.routing import register_routes

ROUTERS = (customer_router, admin_router, retailer_router)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
    app.include_router(root_router)
