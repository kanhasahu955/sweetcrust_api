from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.controllers import routing as ctrl
from app.deps import AsyncSessionDep, AdminUser
from package.common.schemas import ok

from app.controllers.routing_async import RoutingController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await RoutingController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["routing"])

class OptimizeIn(BaseModel):
    order_ids: list[int] | None = None

class AssignIn(BaseModel):
    order_id: int
    delivery_person_id: int

@router.get("/routing/status")
async def get_routing_status():
    return ok({"service": "ready", "mode": "async-oop"})

@router.get("/admin/routing/live")
async def get_routing_live(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.live))

@router.get("/admin/routing/stops")
async def get_routing_stops(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.stops))

@router.post("/admin/routing/optimize")
async def post_routing_optimize(body: OptimizeIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.optimize, body.order_ids))

@router.get("/admin/routing/orders/{order_id}/eta")
async def get_order_id_eta(order_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.eta, order_id))

@router.post("/admin/routing/assign")
async def post_routing_assign(body: AssignIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.assign, body.order_id, body.delivery_person_id))
