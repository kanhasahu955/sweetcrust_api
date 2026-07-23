"""Customer marketplace: approved shops + their products."""
from __future__ import annotations

from sqlmodel import Session, col, func, select

from app.models.catalog import Product
from app.models.user import RetailerProfile
from package.common.errors import NotFoundError
from package.common.shop_hours import enforce_auto_close


def _shop_dict(profile: RetailerProfile, product_count: int = 0) -> dict:
    return {
        "user_id": profile.user_id,
        "shop_name": profile.shop_name,
        "owner_name": profile.owner_name,
        "shop_logo_url": profile.shop_logo_url,
        "village": profile.village,
        "area": profile.area,
        "city": profile.city,
        "pincode": profile.pincode,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "contact_phone": profile.contact_phone,
        "is_open": profile.is_open,
        "shop_open_time": profile.shop_open_time,
        "shop_close_time": profile.shop_close_time,
        "shop_days": profile.shop_days,
        "is_wholesaler": profile.is_wholesaler,
        "product_count": product_count,
    }


def _apply_hours(session: Session, profiles: list[RetailerProfile]) -> None:
    dirty = False
    for p in profiles:
        if enforce_auto_close(p):
            session.add(p)
            dirty = True
    if dirty:
        session.commit()


def list_shops(session: Session) -> list[dict]:
    profiles = list(
        session.exec(
            select(RetailerProfile).where(
                RetailerProfile.approval_status == "approved",
                RetailerProfile.is_blocked == False,  # noqa: E712
            ).order_by(RetailerProfile.shop_name)
        ).all()
    )
    if not profiles:
        return []
    _apply_hours(session, profiles)
    counts: dict[int, int] = {}
    rows = session.exec(
        select(Product.supplier_user_id, func.count(Product.id))
        .where(
            Product.is_active == True,  # noqa: E712
            Product.is_draft == False,  # noqa: E712
            col(Product.supplier_user_id).is_not(None),
        )
        .group_by(Product.supplier_user_id)
    ).all()
    for uid, n in rows:
        if uid is not None:
            counts[int(uid)] = int(n)
    return [_shop_dict(p, counts.get(p.user_id, 0)) for p in profiles]


def shop_detail(session: Session, shop_user_id: int) -> dict:
    profile = session.exec(
        select(RetailerProfile).where(
            RetailerProfile.user_id == shop_user_id,
            RetailerProfile.approval_status == "approved",
            RetailerProfile.is_blocked == False,  # noqa: E712
        )
    ).first()
    if not profile:
        raise NotFoundError("Shop not found")
    _apply_hours(session, [profile])
    products = list(
        session.exec(
            select(Product)
            .where(
                Product.supplier_user_id == shop_user_id,
                Product.is_active == True,  # noqa: E712
                Product.is_draft == False,  # noqa: E712
            )
            .order_by(Product.name)
        ).all()
    )
    return {
        **_shop_dict(profile, len(products)),
        "products": products,
    }
