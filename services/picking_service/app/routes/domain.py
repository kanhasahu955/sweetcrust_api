from __future__ import annotations
from fastapi import APIRouter
from app.controllers import picking as ctrl
from app.deps import AsyncSessionDep, AdminUser
from package.common.schemas import ok

from app.controllers.picking_async import PickingController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await PickingController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["picking"])

@router.get("/picking/status")
async def get_picking_status():
    return ok({"service": "ready", "mode": "async-oop"})

@router.get("/admin/picking/queue")
async def get_picking_queue(session: AsyncSessionDep, _: AdminUser, status: str | None = None):
    return ok(await _domain(session, ctrl.queue, status))

@router.get("/admin/picking/orders/{order_id}")
async def get_orders_order_id(order_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.detail, order_id))

@router.post("/admin/picking/orders/{order_id}/start")
async def post_order_id_start(order_id: int, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, ctrl.start, order_id, admin.id))

@router.post("/admin/picking/orders/{order_id}/pack")
async def post_order_id_pack(order_id: int, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, ctrl.pack, order_id, admin.id))

@router.get("/admin/picking/stats")
async def get_picking_stats(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.stats))
