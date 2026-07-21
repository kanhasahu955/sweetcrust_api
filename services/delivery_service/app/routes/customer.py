"""Customer delivery check — gateway /api/v1/customer/delivery/check."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import SessionDep
from app.services import radius as radius_ops
from package.common.schemas import ok

router = APIRouter(prefix="/customer/delivery", tags=["customer-delivery"])


@router.post("/check")
def delivery_check(body: dict, session: SessionDep):
    lat = body.get("lat") or body.get("latitude")
    lng = body.get("lng") or body.get("longitude")
    if lat is None or lng is None:
        return ok({"deliverable": False, "detail": "lat and lng required"})
    return ok(radius_ops.check_delivery(session, float(lat), float(lng)))
