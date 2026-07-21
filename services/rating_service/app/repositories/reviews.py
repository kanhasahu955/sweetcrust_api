"""Product review persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.catalog import Product, ProductReview

def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)

def list_for_product(session: Session, product_id: int, limit: int = 20) -> list[ProductReview]:
    return list(session.exec(
        select(ProductReview).where(ProductReview.product_id == product_id).order_by(ProductReview.id.desc()).limit(limit)
    ).all())

def save(session: Session, obj):
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
