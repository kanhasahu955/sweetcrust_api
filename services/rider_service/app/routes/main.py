"""Main route table for rider_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.customer import router as customer_router
from app.routes.delivery import router as delivery_router
from package.common.routing import register_routes

ROUTERS = (delivery_router, customer_router)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
