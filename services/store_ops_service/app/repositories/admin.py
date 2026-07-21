"""Store-ops shared lookups."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Product
from app.models.commerce import Order
from app.models.ops import DeliveryPerson, DeliveryTracking
from app.models.user import User


def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)


def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)


def list_riders(session: Session) -> list[DeliveryPerson]:
    return list(session.exec(select(DeliveryPerson).order_by(DeliveryPerson.created_at.desc())).all())


def live_tracks(session: Session) -> list[DeliveryTracking]:
    return list(session.exec(select(DeliveryTracking)).all())
