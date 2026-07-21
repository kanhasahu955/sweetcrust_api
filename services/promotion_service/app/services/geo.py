"""Local delivery radius check (copied from monolith delivery_service; no HTTP hop)."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.ops import BakerySettings
from app.config import get_settings
from package.common.errors import BadRequestError
from package.common.utils import haversine_km


def bakery_coords(session: Session) -> tuple[float, float]:
    s = session.exec(select(BakerySettings)).first()
    if s:
        return s.latitude, s.longitude
    return 19.1197, 72.8468


def check_delivery(session: Session, lat: float, lng: float) -> dict:
    max_km = get_settings().delivery_radius_km
    blat, blng = bakery_coords(session)
    distance = haversine_km(blat, blng, lat, lng)
    return {
        "deliverable": distance <= max_km,
        "distance_km": distance,
        "max_km": max_km,
        "bakery_lat": blat,
        "bakery_lng": blng,
    }


def assert_within_radius(session: Session, lat: float | None, lng: float | None) -> dict:
    if lat is None or lng is None:
        raise BadRequestError("Delivery address must include map location (latitude/longitude)")
    result = check_delivery(session, lat, lng)
    if not result["deliverable"]:
        raise BadRequestError(
            f"Sorry, we only deliver within {result['max_km']:.0f} km of the bakery "
            f"(your location is {result['distance_km']} km away)."
        )
    return result
