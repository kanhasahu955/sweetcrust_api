"""Rider HTTP adapters."""
from __future__ import annotations

from sqlmodel import Session

from app.services import radius as radius_ops
from app.services import rider as rider_ops


def me(session: Session, user):
    return rider_ops.get_delivery_profile(session, user)


def my_orders(session: Session, user):
    return rider_ops.my_orders(session, user)


def update_availability(session: Session, user, is_available: bool):
    return rider_ops.update_availability(session, user, is_available)


def update_location(session: Session, user, **kwargs):
    return rider_ops.update_location(session, user, **kwargs)


def mark_delivered(session: Session, user, order_id: int):
    return rider_ops.mark_delivered(session, user, order_id)


def check_delivery(session: Session, lat: float, lng: float):
    return radius_ops.check_delivery(session, lat, lng)
