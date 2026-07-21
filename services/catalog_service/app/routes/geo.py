"""Public geo helpers — Google Places Autocomplete + Geocoding."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import geo as geo_ops
from package.common.schemas import ok
from package.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/suggest")
def suggest(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(6, ge=1, le=10),
    session_token: str | None = Query(None),
):
    return ok(geo_ops.suggest_addresses(q, limit=limit, session_token=session_token))


@router.get("/place/{place_id}")
def place(place_id: str, session_token: str | None = Query(None)):
    data = geo_ops.place_details(place_id, session_token=session_token)
    if not data:
        raise HTTPException(404, "Place not found")
    return ok(data)


@router.get("/reverse")
def reverse(lat: float = Query(...), lng: float = Query(...)):
    data = geo_ops.reverse_geocode(lat, lng)
    if not data:
        raise HTTPException(404, "No address for coordinates")
    return ok(data)


@router.get("/pincode/{pin}")
def pincode(pin: str):
    data = geo_ops.lookup_pincode(pin)
    if not data:
        return ok({"ok": False, "detail": "Pincode not found"})
    filled = geo_ops.geocode_fill(data)
    return ok({"ok": True, **filled})
