"""Routing data access — orders, tracking, riders, bakery settings."""
from __future__ import annotations
from sqlmodel import Session, col, select
from app.models.commerce import Order
from app.models.enums import OrderStatus
from app.models.ops import BakerySettings, DeliveryPerson, DeliveryTracking

def bakery_settings(session: Session) -> BakerySettings | None:
    return session.exec(select(BakerySettings)).first()

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def get_rider(session: Session, person_id: int) -> DeliveryPerson | None:
    return session.get(DeliveryPerson, person_id)

def get_tracking(session: Session, order_id: int) -> DeliveryTracking | None:
    return session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order_id)).first()

def list_tracking(session: Session) -> list[DeliveryTracking]:
    return list(session.exec(select(DeliveryTracking)).all())

def open_orders(session: Session) -> list[Order]:
    return list(session.exec(select(Order).where(
        col(Order.status).in_([OrderStatus.PACKED, OrderStatus.DELIVERY_ASSIGNED, OrderStatus.OUT_FOR_DELIVERY])
    ).limit(100)).all())

def save_order(session: Session, order: Order) -> Order:
    session.add(order)
    session.commit()
    session.refresh(order)
    return order

def save_tracking(session: Session, track: DeliveryTracking) -> DeliveryTracking:
    session.add(track)
    session.commit()
    session.refresh(track)
    return track
