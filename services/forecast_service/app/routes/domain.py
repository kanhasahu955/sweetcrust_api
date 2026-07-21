from __future__ import annotations
from fastapi import APIRouter
from app.controllers import forecast as ctrl
from app.deps import AsyncSessionDep, AdminUser
from package.common.schemas import ok

from app.controllers.forecast_async import ForecastController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await ForecastController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["forecast"])

@router.get("/forecast/status")
async def get_forecast_status():
    return ok({"service": "ready", "mode": "async-oop"})

@router.get("/admin/forecast/demand")
async def get_forecast_demand(session: AsyncSessionDep, _: AdminUser, period: str = "weekly"):
    return ok(await _domain(session, ctrl.demand, period))

@router.get("/admin/forecast/stockout")
async def get_forecast_stockout(session: AsyncSessionDep, _: AdminUser, period: str = "weekly"):
    return ok(await _domain(session, ctrl.stockout, period))

@router.get("/admin/forecast/revenue")
async def get_forecast_revenue(session: AsyncSessionDep, _: AdminUser, period: str = "weekly"):
    return ok(await _domain(session, ctrl.revenue, period))

@router.get("/admin/forecast/sku/{product_id}")
async def get_sku_product_id(product_id: int, session: AsyncSessionDep, _: AdminUser, period: str = "weekly"):
    return ok(await _domain(session, ctrl.sku, product_id, period))
