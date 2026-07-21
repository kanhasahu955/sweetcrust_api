"""Dispatch — orders + live tracking."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Order
from app.models.ops import DeliveryTracking

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def live_tracks(session: Session) -> list[DeliveryTracking]:
    return list(session.exec(select(DeliveryTracking)).all())
