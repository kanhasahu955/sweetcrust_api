"""Inventory / stock movement access."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.catalog import Product, StockMovement
from app.models.enums import StockStatus

def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)

def active_products(session: Session) -> list[Product]:
    return list(session.exec(select(Product).where(Product.is_active == True)).all())  # noqa: E712

def movements(session: Session, product_id: int | None = None, limit: int = 50) -> list[StockMovement]:
    stmt = select(StockMovement).order_by(StockMovement.id.desc()).limit(min(limit, 200))
    if product_id is not None:
        stmt = select(StockMovement).where(StockMovement.product_id == product_id).order_by(StockMovement.id.desc()).limit(min(limit, 200))
    return list(session.exec(stmt).all())

def low_stock(session: Session) -> list[Product]:
    return [p for p in active_products(session) if p.stock_status in (StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK)]
