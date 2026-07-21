from __future__ import annotations

from sqlmodel import Session, select

from app.producers.events import emit_delivery_location
from app.models.ops import DeliveryPerson, DeliveryTracking
from app.schemas.admin import DeliveryPersonIn, DeliveryPersonPatchIn
from package.common.errors import NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def list_persons(session: Session):
    return list(session.exec(select(DeliveryPerson).order_by(DeliveryPerson.created_at.desc())).all())


def create_person(session: Session, body: DeliveryPersonIn) -> DeliveryPerson:
    p = DeliveryPerson(
        name=body.name,
        phone=body.phone,
        vehicle_number=body.vehicle_number,
        default_trip_cost=body.default_trip_cost,
        is_available=body.is_available,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    logger.info("delivery person created id=%s", p.id)
    return p


def patch_person(session: Session, person_id: int, body: DeliveryPersonPatchIn) -> DeliveryPerson:
    p = session.get(DeliveryPerson, person_id)
    if not p:
        raise NotFoundError("Delivery person not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def live(session: Session):
    return list(session.exec(select(DeliveryTracking)).all())


def update_location(session: Session, order_id: int, lat: float, lng: float, eta: int | None = None):
    track = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order_id)).first()
    if not track:
        raise NotFoundError("Tracking not found")
    track.rider_lat = lat
    track.rider_lng = lng
    if eta is not None:
        track.eta_minutes = eta
    track.updated_at = utc_now()
    session.add(track)
    session.commit()
    session.refresh(track)
    emit_delivery_location(
        order_id,
        {
            "lat": lat,
            "lng": lng,
            "eta_minutes": track.eta_minutes,
            "delivery_person_id": track.delivery_person_id,
        },
    )
    return track
