"""Checkout reads — cart, address, products."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Address, Cart, CartItem, Order

def get_cart(session: Session, user_id: int) -> Cart | None:
    return session.exec(select(Cart).where(Cart.user_id == user_id)).first()

def get_address(session: Session, address_id: int) -> Address | None:
    return session.get(Address, address_id)

def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)
