from __future__ import annotations
from fastapi import APIRouter, Query
from app.controllers import location as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.commerce import AddressIn
from package.common.schemas import ok

from app.controllers.location_async import LocationController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await LocationController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["location"])

@router.get("/customer/addresses")
async def get_customer_addresses(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.list_addresses, user.id))

@router.post("/customer/addresses")
async def post_customer_addresses(body: AddressIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.add_address, user, body))

@router.delete("/customer/addresses/{address_id}")
async def delete_addresses_address_id(address_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.delete_address, user.id, address_id))

@router.get("/geo/suggest")
async def get_geo_suggest(q: str = Query(...), limit: int = 6, session_token: str | None = None):
    return ok(ctrl.suggest(q, limit=limit, session_token=session_token))

@router.get("/geo/place/{place_id}")
async def get_place_place_id(place_id: str, session_token: str | None = None):
    return ok(ctrl.place(place_id, session_token=session_token))

@router.get("/geo/reverse")
async def get_geo_reverse(lat: float, lng: float):
    return ok(ctrl.reverse(lat, lng))

@router.get("/geo/pincode/{pin}")
async def get_pincode_pin(pin: str):
    return ok(ctrl.pincode(pin))
