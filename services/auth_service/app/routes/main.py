"""Main route table for auth_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.auth import router as auth_router
from package.common.routing import register_routes

ROUTERS = (auth_router,)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
