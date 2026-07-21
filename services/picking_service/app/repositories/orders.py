"""Picking order / line-item access."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Order, OrderItem

def get(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def list_recent(session: Session, limit: int = 500) -> list[Order]:
    return list(session.exec(select(Order).order_by(Order.created_at.desc()).limit(limit)).all())

def list_oldest(session: Session, limit: int = 200) -> list[Order]:
    return list(session.exec(select(Order).order_by(Order.created_at.asc()).limit(limit)).all())

def items_for(session: Session, order_id: int) -> list[OrderItem]:
    return list(session.exec(select(OrderItem).where(OrderItem.order_id == order_id)).all())

def save(session: Session, order: Order) -> Order:
    session.add(order)
    session.commit()
    session.refresh(order)
    return order
