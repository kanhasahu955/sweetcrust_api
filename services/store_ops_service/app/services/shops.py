from __future__ import annotations

from sqlmodel import Session, select

from app.models.enums import UserRole
from app.models.user import RetailerProfile, User
from app.services.phone import normalize_phone
from app.schemas.admin import ShopCreateIn, ShopPatchIn
from app.producers.events import emit_admin_event, emit_user_event
from package.common.errors import BadRequestError, ConflictError, NotFoundError
from package.common.shop_hours import enforce_auto_close
from package.common.utils import hash_password
from package.logger import get_logger

logger = get_logger(__name__)


def _address_display(p: RetailerProfile) -> str | None:
    parts = [p.address_line, p.village, p.area, p.city, p.pincode]
    joined = ", ".join(str(x).strip() for x in parts if x and str(x).strip())
    return joined or None


def list_shops(session: Session) -> list[dict]:
    rows = session.exec(select(RetailerProfile)).all()
    dirty = False
    out = []
    for p in rows:
        if enforce_auto_close(p):
            session.add(p)
            dirty = True
        u = session.get(User, p.user_id)
        limit = float(p.credit_limit or 0)
        owed = float(p.outstanding_balance or 0)
        is_supplier = bool(p.is_wholesaler)
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
                "pincode": p.pincode,
                "address_line": p.address_line,
                "address_display": _address_display(p),
                "credit_allowed": p.credit_allowed,
                "credit_limit": limit,
                "credit_remaining": max(0.0, round(limit - owed, 2)),
                "outstanding_balance": owed,
                "payable_balance": float(p.payable_balance or 0),
                "is_wholesaler": p.is_wholesaler,
                "is_supplier": is_supplier,
                "is_blocked": bool(p.is_blocked),
                "approval_status": p.approval_status or "approved",
                "sell_subscription_status": getattr(p, "sell_subscription_status", None) or "none",
                "gstin": p.gstin,
                "contact_phone": p.contact_phone,
                "aadhaar_number": p.aadhaar_number,
                "aadhaar_url": p.aadhaar_url,
                "pan_number": p.pan_number,
                "pan_url": p.pan_url,
                "shop_logo_url": p.shop_logo_url,
                "shop_days": p.shop_days,
                "shop_open_time": p.shop_open_time,
                "shop_close_time": p.shop_close_time,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "is_open": p.is_open,
                "is_online": bool(u.is_online) if u else False,
                "last_seen_at": getattr(u, "last_seen_at", None).isoformat()
                if getattr(u, "last_seen_at", None)
                else None,
            }
        )
    if dirty:
        session.commit()
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
    payload = {
        "user_id": profile.user_id,
        "shop_name": profile.shop_name,
        "approval_status": "approved",
        "credit_allowed": bool(profile.credit_allowed),
        "credit_limit": float(profile.credit_limit or 0),
    }
    emit_admin_event("shop_approved", payload)
    emit_user_event(profile.user_id, "shop_status", payload)
    return {"user_id": profile.user_id, "approval_status": "approved", "message": "Shop approved"}


def set_sell_subscription(session: Session, retailer_user_id: int, status: str) -> dict:
    from datetime import timedelta

    from package.common.utils import utc_now

    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == retailer_user_id)).first()
    if not profile:
        raise NotFoundError("Shop not found")
    status = (status or "").strip().lower()
    if status not in {"approved", "rejected", "pending", "none", "expired"}:
        raise BadRequestError("status must be approved|rejected|pending|none|expired")
    profile.sell_subscription_status = status
    if status == "approved":
        # Admin comp / override — grant 30 days if no expiry set
        if not getattr(profile, "sell_subscription_expires_at", None):
            profile.sell_plan = profile.sell_plan or "monthly"
            profile.sell_subscription_expires_at = utc_now() + timedelta(days=30)
        profile.sell_rz_pending = None
    session.add(profile)
    session.commit()
    emit_user_event(
        profile.user_id,
        "sell_subscription",
        {
            "sell_subscription_status": status,
            "shop_name": profile.shop_name,
            "sell_plan": getattr(profile, "sell_plan", None),
        },
    )
    return {
        "user_id": profile.user_id,
        "sell_subscription_status": status,
        "sell_plan": getattr(profile, "sell_plan", None),
        "message": f"Sell subscription set to {status}",
    }


def reject_shop(session: Session, retailer_user_id: int) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == retailer_user_id)).first()
    if not profile:
        raise NotFoundError("Shop not found")
    profile.approval_status = "rejected"
    session.add(profile)
    session.commit()
    payload = {
        "user_id": profile.user_id,
        "shop_name": profile.shop_name,
        "approval_status": "rejected",
    }
    emit_admin_event("shop_rejected", payload)
    emit_user_event(profile.user_id, "shop_status", payload)
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
