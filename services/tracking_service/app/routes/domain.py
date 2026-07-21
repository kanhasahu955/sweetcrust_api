from __future__ import annotations
from fastapi import APIRouter
from app.controllers import tracking as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from package.common.schemas import ok

from app.controllers.tracking_async import TrackingController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await TrackingController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["tracking"])

@router.get("/customer/orders/{order_id}/track")
async def get_order_id_track(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.track, order_id, user.id))

@router.post("/customer/orders/{order_id}/share-track")
async def post_order_id_share_track(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.share, user, order_id))

@router.get("/customer/track/share/{token}")
async def get_share_token(token: str, session: AsyncSessionDep):
    return ok(await _domain(session, ctrl.public_track, token))
