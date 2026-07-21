"""Cart persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Cart, CartItem
from app.models.catalog import Product

def get_cart(session: Session, user_id: int) -> Cart | None:
    return session.exec(select(Cart).where(Cart.user_id == user_id)).first()

def get_item(session: Session, item_id: int) -> CartItem | None:
    return session.get(CartItem, item_id)

def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)

def items_for_cart(session: Session, cart_id: int, *, saved: bool | None = None) -> list[CartItem]:
    stmt = select(CartItem).where(CartItem.cart_id == cart_id)
    if saved is not None:
        stmt = stmt.where(CartItem.saved_for_later == saved)
    return list(session.exec(stmt).all())

def save(session: Session, obj):
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj

def delete(session: Session, obj) -> None:
    session.delete(obj)
    session.commit()
