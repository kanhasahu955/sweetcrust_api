"""Main route table for catalog_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.customer import router as customer_router
from app.routes.geo import router as geo_router
from package.common.routing import register_routes

ROUTERS = (customer_router, geo_router)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
