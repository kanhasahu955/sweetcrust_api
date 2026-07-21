"""Rider / delivery assignment access."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Order
from app.models.ops import DeliveryPerson, DeliveryTracking
from app.models.user import User

def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)

def get_person_by_user(session: Session, user_id: int) -> DeliveryPerson | None:
    return session.exec(select(DeliveryPerson).where(DeliveryPerson.user_id == user_id)).first()

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def get_tracking(session: Session, order_id: int) -> DeliveryTracking | None:
    return session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order_id)).first()
