"""Invoice persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Invoice, Order

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def for_order(session: Session, order_id: int) -> Invoice | None:
    return session.exec(select(Invoice).where(Invoice.order_id == order_id)).first()
