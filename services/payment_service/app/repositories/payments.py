"""Payment persistence helpers."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Order, Payment

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def list_for_order(session: Session, order_id: int) -> list[Payment]:
    return list(session.exec(select(Payment).where(Payment.order_id == order_id)).all())

def save(session: Session, obj):
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
