"""Coupon persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Coupon

def list_all(session: Session) -> list[Coupon]:
    return list(session.exec(select(Coupon).order_by(Coupon.created_at.desc())).all())

def get(session: Session, coupon_id: int) -> Coupon | None:
    return session.get(Coupon, coupon_id)

def get_by_code(session: Session, code: str) -> Coupon | None:
    return session.exec(select(Coupon).where(Coupon.code == code.strip().upper())).first()

def save(session: Session, coupon: Coupon) -> Coupon:
    session.add(coupon)
    session.commit()
    session.refresh(coupon)
    return coupon
