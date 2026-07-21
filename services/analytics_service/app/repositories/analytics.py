"""Analytics data access helpers used by dashboard/misc services."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.commerce import Order, OrderItem, Payment


def orders_since(session: Session, since: datetime) -> list[Order]:
    return list(session.exec(select(Order).where(Order.created_at >= since)).all())


def payments_since(session: Session, since: datetime) -> list[Payment]:
    return list(session.exec(select(Payment).where(Payment.created_at >= since)).all())


def items_for_orders(session: Session, order_ids: list[int]) -> list[OrderItem]:
    if not order_ids:
        return []
    return list(session.exec(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).all())
