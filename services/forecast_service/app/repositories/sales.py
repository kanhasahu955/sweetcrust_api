"""Forecast data access — orders, items, products."""
from __future__ import annotations
from datetime import datetime
from sqlmodel import Session, select
from app.models.catalog import Product
from app.models.commerce import Order, OrderItem

def orders_since(session: Session, since: datetime) -> list[Order]:
    return list(session.exec(select(Order).where(Order.created_at >= since)).all())

def items_for_orders(session: Session, order_ids: list[int]) -> list[OrderItem]:
    if not order_ids:
        return []
    return list(session.exec(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).all())

def active_products(session: Session) -> list[Product]:
    return list(session.exec(select(Product).where(Product.is_active == True)).all())  # noqa: E712

def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)

def items_for_product(session: Session, order_ids: list[int], product_id: int) -> list[OrderItem]:
    if not order_ids:
        return []
    return list(session.exec(
        select(OrderItem).where(OrderItem.order_id.in_(order_ids), OrderItem.product_id == product_id)
    ).all())
