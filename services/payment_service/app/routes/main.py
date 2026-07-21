"""Main route table for payment_service."""
from __future__ import annotations
from fastapi import FastAPI
from app.routes.customer import router as customer_router
from app.routes.payments import router as payments_router
from package.common.routing import register_routes

ROUTERS = (payments_router, customer_router)

def mount(app: FastAPI) -> None:
    register_routes(app, ROUTERS, api_prefix="/api/v1")
