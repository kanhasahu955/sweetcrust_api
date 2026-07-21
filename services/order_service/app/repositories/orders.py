"""Order persistence helpers."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Invoice, Order, OrderItem, ReturnRequest

def get(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def list_for_user(session: Session, user_id: int, limit: int = 100) -> list[Order]:
    return list(session.exec(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)).all())

def items(session: Session, order_id: int) -> list[OrderItem]:
    return list(session.exec(select(OrderItem).where(OrderItem.order_id == order_id)).all())

def get_invoice(session: Session, order_id: int) -> Invoice | None:
    return session.exec(select(Invoice).where(Invoice.order_id == order_id)).first()

def returns_for_user(session: Session, user_id: int) -> list[ReturnRequest]:
    return list(session.exec(select(ReturnRequest).where(ReturnRequest.user_id == user_id)).all())

def save(session: Session, obj):
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
