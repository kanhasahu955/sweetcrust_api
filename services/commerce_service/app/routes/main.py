"""Main route table for commerce_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.routes import router as domain_router
from package.common.routing import register_routes

ROUTERS = (domain_router,)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
