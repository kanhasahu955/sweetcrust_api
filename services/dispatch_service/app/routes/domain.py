from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.controllers import dispatch as ctrl
from app.deps import AsyncSessionDep, AdminUser
from package.common.schemas import ok

from app.controllers.dispatch_async import DispatchController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await DispatchController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/admin", tags=["dispatch"])

class AssignIn(BaseModel):
    delivery_person_id: int

class StatusIn(BaseModel):
    status: str
    note: str | None = None
    delivery_person_id: int | None = None

@router.get("/delivery/live")
async def get_delivery_live(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.live))

@router.post("/orders/{order_id}/assign-delivery")
async def post_order_id_assign_delivery(order_id: int, body: AssignIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, ctrl.assign, order_id, body.delivery_person_id, admin.id))

@router.patch("/orders/{order_id}/status")
async def patch_order_id_status(order_id: int, body: StatusIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, ctrl.update_status, order_id, body.status, admin.id, body.note, body.delivery_person_id))
