from __future__ import annotations
from fastapi import APIRouter
from app.controllers import analytics as ctrl
from app.deps import AsyncSessionDep, AdminUser
from package.common.schemas import ok

from app.controllers.analytics_async import AnalyticsController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await AnalyticsController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/admin", tags=["analytics"])

@router.get("/dashboard")
async def get_dashboard(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.dashboard))

@router.get("/reports")
async def get_reports(session: AsyncSessionDep, _: AdminUser, period: str = "weekly"):
    return ok(await _domain(session, ctrl.reports, period))
