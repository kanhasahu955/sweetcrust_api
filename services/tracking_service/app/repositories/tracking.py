"""Tracking / share-link access."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Order
from app.models.engagement import ShareTrackLink

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def get_share(session: Session, token: str) -> ShareTrackLink | None:
    return session.exec(select(ShareTrackLink).where(ShareTrackLink.token == token)).first()
