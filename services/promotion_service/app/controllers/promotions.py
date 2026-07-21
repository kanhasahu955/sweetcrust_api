"""Promotion HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import orders as order_ops
from app.services import promotions as promo_ops

def apply_coupon(session: Session, user_id: int, code: str):
    return order_ops.apply_coupon(session, user_id, code)

def validate(session: Session, code: str, subtotal: float = 0):
    return promo_ops.validate_code(session, code, subtotal)

def list_coupons(session: Session, active_only: bool = False):
    return promo_ops.list_coupons(session, active_only=active_only)

def create_coupon(session: Session, data: dict):
    return promo_ops.create_coupon(session, data)

def set_active(session: Session, coupon_id: int, is_active: bool):
    return promo_ops.set_active(session, coupon_id, is_active)
