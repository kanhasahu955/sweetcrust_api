from __future__ import annotations
from sqlmodel import Session
from app.models.commerce import Coupon
from app.repositories import coupons as coupon_repo
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now

def list_coupons(session: Session, *, active_only: bool = False) -> list[Coupon]:
    rows = coupon_repo.list_all(session)
    if active_only:
        rows = [c for c in rows if c.is_active]
    return rows

def create_coupon(session: Session, data: dict) -> Coupon:
    code = (data.get("code") or "").strip().upper()
    if not code:
        raise BadRequestError("code required")
    if coupon_repo.get_by_code(session, code):
        raise BadRequestError("Coupon code already exists")
    c = Coupon(
        code=code, title=data.get("title") or code, description=data.get("description"),
        coupon_type=data.get("coupon_type") or "percentage", value=float(data.get("value") or 0),
        min_order_amount=float(data.get("min_order_amount") or 0), max_discount=data.get("max_discount"),
        is_active=bool(data.get("is_active", True)),
    )
    return coupon_repo.save(session, c)

def set_active(session: Session, coupon_id: int, is_active: bool) -> Coupon:
    c = coupon_repo.get(session, coupon_id)
    if not c:
        raise NotFoundError("Coupon not found")
    c.is_active = is_active
    return coupon_repo.save(session, c)

def validate_code(session: Session, code: str, subtotal: float = 0) -> dict:
    c = coupon_repo.get_by_code(session, code)
    if not c or not c.is_active:
        raise NotFoundError("Coupon not found or inactive")
    if c.min_order_amount and subtotal < c.min_order_amount:
        raise BadRequestError(f"Minimum order ₹{c.min_order_amount:.0f} required")
    discount = c.value if c.coupon_type == "flat" else round(subtotal * (c.value / 100), 2)
    if c.max_discount is not None:
        discount = min(discount, float(c.max_discount))
    return {"coupon": c, "discount": discount, "validated_at": utc_now().isoformat()}
