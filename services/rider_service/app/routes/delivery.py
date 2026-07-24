"""Delivery rider API — JWT role=delivery required."""
from __future__ import annotations
from fastapi import APIRouter
from app.controllers import rider as ctrl
from app.deps import DeliveryUser, AsyncSessionDep
from app.schemas.delivery import AvailabilityIn, RiderLocationIn, RiderStatusIn
from package.common.schemas import ok
from app.controllers.rider_async import RiderController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await RiderController(session).call(fn, *args, **kwargs)

router = APIRouter(prefix='/delivery', tags=['delivery'])

@router.get('/me')
async def me(session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.me, user))

@router.get('/orders')
async def orders(session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.my_orders, user))

@router.patch('/availability')
async def availability(body: AvailabilityIn, session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.update_availability, user, body.is_available))

@router.post('/location')
async def location(body: RiderLocationIn, session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.update_location, user, lat=body.lat, lng=body.lng, order_id=body.order_id, eta_minutes=body.eta_minutes, distance_km=body.distance_km))

@router.post('/orders/{order_id}/accept')
async def accept(order_id: int, session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.accept_order, user, order_id))

@router.post('/orders/{order_id}/reject')
async def reject(order_id: int, session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.reject_order, user, order_id))

@router.post('/orders/{order_id}/status')
async def status(order_id: int, body: RiderStatusIn, session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.update_order_status, user, order_id, body.status))

@router.post('/orders/{order_id}/delivered')
async def delivered(order_id: int, session: AsyncSessionDep, user: DeliveryUser):
    return ok(await _domain(session, ctrl.mark_delivered, user, order_id))
