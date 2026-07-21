from __future__ import annotations
from fastapi import APIRouter, Query
from app.controllers import orders as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.commerce import CustomCakeIn, OrderRateIn, ReturnIn
from package.common.schemas import ok

from app.controllers.order_async import OrderController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await OrderController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/customer", tags=["orders"])

@router.get("/orders")
async def get_orders(session: AsyncSessionDep, user: CurrentUser, tab: str = Query("active")):
    return ok(await _domain(session, ctrl.list_orders, user.id, tab))

@router.get("/orders/{order_id}")
async def get_orders_order_id(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.detail, order_id, user.id))

@router.post("/orders/{order_id}/cancel")
async def post_order_id_cancel(order_id: int, session: AsyncSessionDep, user: CurrentUser, reason: str = "Changed mind"):
    return ok(await _domain(session, ctrl.cancel, order_id, user.id, reason))

@router.post("/orders/{order_id}/reorder")
async def post_order_id_reorder(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.reorder, order_id, user.id))

@router.get("/orders/{order_id}/invoice")
async def get_order_id_invoice(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.invoice, order_id, user.id))

@router.post("/orders/{order_id}/rate")
async def post_order_id_rate(order_id: int, body: OrderRateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.rate, order_id, user.id, body.rating, body.comment))

@router.get("/orders/{order_id}/track")
async def get_order_id_track(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.track, order_id, user.id))

@router.post("/orders/{order_id}/share-track")
async def post_order_id_share_track(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.share_track, user, order_id))

@router.post("/custom-cakes")
async def post_custom_cakes(body: CustomCakeIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.create_cake, user.id, body))

@router.get("/custom-cakes")
async def get_custom_cakes(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.list_cakes, user.id))

@router.post("/returns")
async def post_returns(body: ReturnIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.create_return, user.id, body))

@router.get("/returns")
async def get_returns(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.list_returns, user.id))

@router.get("/returns/{return_id}")
async def get_returns_return_id(return_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.return_detail, return_id, user.id))
