from __future__ import annotations

from sqlmodel import Session, select

from app.models.enums import UserRole
from app.models.user import RetailerProfile, User
from app.services.phone import normalize_phone
from app.schemas.admin import ShopCreateIn, ShopPatchIn
from package.common.errors import BadRequestError, ConflictError, NotFoundError
from package.common.utils import hash_password
from package.logger import get_logger

logger = get_logger(__name__)


def list_shops(session: Session) -> list[dict]:
    rows = session.exec(select(RetailerProfile)).all()
    out = []
    for p in rows:
        u = session.get(User, p.user_id)
        out.append(
            {
                "user_id": p.user_id,
                "shop_name": p.shop_name,
                "owner_name": p.owner_name or (u.name if u else None),
                "phone": u.phone if u else None,
                "email": u.email if u else None,
                "village": p.village,
                "area": p.area,
                "city": p.city,
                "state": p.state,
                "zone": p.zone,
                "credit_allowed": p.credit_allowed,
                "credit_limit": p.credit_limit,
                "outstanding_balance": p.outstanding_balance,
                "payable_balance": p.payable_balance,
                "is_wholesaler": p.is_wholesaler,
                "is_blocked": p.is_blocked,
                "approval_status": p.approval_status or "approved",
                "gstin": p.gstin,
                "contact_phone": p.contact_phone,
                "is_open": p.is_open,
                "is_online": bool(u.is_online) if u else False,
            }
        )
    return out


def create_shop(session: Session, body: ShopCreateIn) -> dict:
    phone = normalize_phone(body.phone)
    if len(body.password) < 6:
        raise BadRequestError("Password must be at least 6 characters")
    if session.exec(select(User).where(User.phone == phone)).first():
        raise ConflictError("Phone already in use")
    user = User(
        phone=phone,
        name=body.owner_name.strip(),
        password_hash=hash_password(body.password),
        role=UserRole.RETAILER,
        terms_accepted=True,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    contact = (body.contact_phone or phone or "").strip() or phone
    profile = RetailerProfile(
        user_id=user.id,
        shop_name=body.shop_name.strip(),
        owner_name=body.owner_name.strip(),
        contact_phone=contact,
        village=body.village,
        area=body.area,
        zone=body.zone,
        city=body.city,
        state=body.state,
        pincode=body.pincode,
        address_line=body.address_line,
        gstin=body.gstin,
        credit_allowed=body.credit_allowed,
        credit_limit=float(body.credit_limit or 0),
        approval_status="approved",
    )
    session.add(profile)
    session.commit()
    logger.info("shop created user_id=%s", user.id)
    return {
        "user_id": user.id,
        "phone": user.phone,
        "shop_name": profile.shop_name,
        "approval_status": "approved",
        "message": "Shop created. Retailer can sign in with phone + password.",
    }


def approve_shop(session: Session, retailer_user_id: int, payload: dict | None = None) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == retailer_user_id)).first()
    if not profile:
        raise NotFoundError("Shop not found")
    payload = payload or {}
    profile.approval_status = "approved"
    profile.is_blocked = False
    if payload.get("credit_allowed") is not None:
        profile.credit_allowed = bool(payload["credit_allowed"])
    if payload.get("credit_limit") is not None:
        profile.credit_limit = float(payload["credit_limit"])
    session.add(profile)
    session.commit()
    return {"user_id": profile.user_id, "approval_status": "approved", "message": "Shop approved"}


def reject_shop(session: Session, retailer_user_id: int) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == retailer_user_id)).first()
    if not profile:
        raise NotFoundError("Shop not found")
    profile.approval_status = "rejected"
    session.add(profile)
    session.commit()
    return {"user_id": profile.user_id, "approval_status": "rejected"}


def patch_shop(session: Session, retailer_user_id: int, body: ShopPatchIn) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == retailer_user_id)).first()
    if not profile:
        raise NotFoundError("Shop not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "contact_phone" and v is not None:
            profile.contact_phone = normalize_phone(str(v))
        elif hasattr(profile, k):
            setattr(profile, k, v)
    session.add(profile)
    session.commit()
    return {"user_id": profile.user_id, "shop_name": profile.shop_name, "message": "Shop updated"}
