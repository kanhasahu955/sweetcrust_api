"""Customer delivery check — gateway /api/v1/customer/delivery/check."""
from __future__ import annotations
from fastapi import APIRouter
from app.controllers import rider as ctrl
from app.deps import AsyncSessionDep
from package.common.schemas import ok
from app.controllers.rider_async import RiderController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await RiderController(session).call(fn, *args, **kwargs)

router = APIRouter(prefix='/customer/delivery', tags=['customer-delivery'])

@router.post('/check')
async def delivery_check(body: dict, session: AsyncSessionDep):
    lat = body.get('lat') or body.get('latitude')
    lng = body.get('lng') or body.get('longitude')
    if lat is None or lng is None:
        return ok({'deliverable': False, 'detail': 'lat and lng required'})
    return ok(await _domain(session, ctrl.check_delivery, float(lat), float(lng)))
