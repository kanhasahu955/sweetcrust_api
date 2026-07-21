"""Delivery rider API — JWT role=delivery required."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import DeliveryUser, SessionDep
from app.services import rider as rider_ops
from app.schemas.delivery import AvailabilityIn, RiderLocationIn
from package.common.schemas import ok

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/me")
def me(session: SessionDep, user: DeliveryUser):
    return ok(rider_ops.get_delivery_profile(session, user))


@router.get("/orders")
def orders(session: SessionDep, user: DeliveryUser):
    return ok(rider_ops.my_orders(session, user))


@router.patch("/availability")
def availability(body: AvailabilityIn, session: SessionDep, user: DeliveryUser):
    return ok(rider_ops.update_availability(session, user, body.is_available))


@router.post("/location")
def location(body: RiderLocationIn, session: SessionDep, user: DeliveryUser):
    return ok(
        rider_ops.update_location(
            session,
            user,
            lat=body.lat,
            lng=body.lng,
            order_id=body.order_id,
            eta_minutes=body.eta_minutes,
            distance_km=body.distance_km,
        )
    )


@router.post("/orders/{order_id}/delivered")
def delivered(order_id: int, session: SessionDep, user: DeliveryUser):
    return ok(rider_ops.mark_delivered(session, user, order_id))
