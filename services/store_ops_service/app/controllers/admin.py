"""Store-ops admin HTTP adapters → domain services."""
from __future__ import annotations

from sqlmodel import Session

from app.services import dashboard as dash_ops
from app.services import delivery as delivery_ops
from app.services import misc as misc_ops
from app.services import orders as order_ops
from app.services import products as product_ops
from app.services import shops as shop_ops


def dashboard(session: Session):
    return dash_ops.dashboard(session)


def reports(session: Session, period: str = "weekly"):
    return misc_ops.reports(session, period)


def inventory(session: Session):
    return misc_ops.inventory(session)


def list_products(session: Session, **kwargs):
    return product_ops.list_products(session, **kwargs)


def list_orders(session: Session, **kwargs):
    return order_ops.list_orders(session, **kwargs)


def live_delivery(session: Session):
    return delivery_ops.live(session)


def list_shops(session: Session):
    return shop_ops.list_shops(session)
