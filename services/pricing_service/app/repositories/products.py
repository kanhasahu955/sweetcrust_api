"""Pricing product reads/writes."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.catalog import Product

def get(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)

def list_all(session: Session) -> list[Product]:
    return list(session.exec(select(Product).order_by(Product.updated_at.desc())).all())

def save(session: Session, product: Product) -> Product:
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
