"""Checkout HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import orders as order_ops

def checkout(session: Session, user_id: int, body):
    order = order_ops.checkout(session, user_id, body)
    return {"order": order, "message": "Order created. Proceed to payment."}
