"""Inventory HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.repositories import stock as stock_repo
from app.services import misc as misc_ops
from app.services import products as product_ops

def summary(session: Session):
    return misc_ops.inventory(session)

def low_stock(session: Session):
    return stock_repo.low_stock(session)

def movements(session: Session, product_id=None, limit=50):
    return stock_repo.movements(session, product_id, limit)

def update_stock(session: Session, product_id: int, stock_qty: int, reason: str, note, admin_id):
    return product_ops.update_stock(session, product_id, stock_qty, reason, note, admin_id)
