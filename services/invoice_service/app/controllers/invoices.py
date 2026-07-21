"""Invoice HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import orders as order_ops

def get_invoice(session: Session, order_id: int, user_id: int):
    return order_ops.get_invoice(session, order_id, user_id)
