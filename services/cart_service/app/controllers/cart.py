"""Cart HTTP adapters → orders cart use-cases."""
from __future__ import annotations
from sqlmodel import Session
from app.services import orders as order_ops

def get_cart(session: Session, user_id: int):
    return order_ops.cart_summary(session, user_id)

def add_item(session: Session, user_id: int, product_id: int, quantity: int, variant=None, flavor=None, is_eggless=False):
    return order_ops.add_to_cart(session, user_id, product_id, quantity, variant, flavor, is_eggless)

def patch_item(session: Session, user_id: int, item_id: int, quantity=None, saved_for_later=None):
    return order_ops.patch_cart_item(session, user_id, item_id, quantity, saved_for_later)

def remove_item(session: Session, user_id: int, item_id: int):
    return order_ops.remove_cart_item(session, user_id, item_id)

def apply_coupon(session: Session, user_id: int, code: str):
    return order_ops.apply_coupon(session, user_id, code)
