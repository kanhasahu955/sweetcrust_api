"""Catalog product data access."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Category, Favorite, Product, ProductReview


def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)


def list_categories(session: Session, *, active_only: bool = True) -> list[Category]:
    q = select(Category)
    if active_only:
        q = q.where(Category.is_active == True)  # noqa: E712
    return list(session.exec(q.order_by(Category.display_order, Category.name)).all())


def list_active_products(session: Session) -> list[Product]:
    return list(
        session.exec(
            select(Product).where(Product.is_active == True, Product.is_draft == False)  # noqa: E712
        ).all()
    )


def reviews_for(session: Session, product_id: int, limit: int = 20) -> list[ProductReview]:
    return list(
        session.exec(
            select(ProductReview).where(ProductReview.product_id == product_id).limit(limit)
        ).all()
    )


def favorite(session: Session, user_id: int, product_id: int) -> Favorite | None:
    return session.exec(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.product_id == product_id)
    ).first()
