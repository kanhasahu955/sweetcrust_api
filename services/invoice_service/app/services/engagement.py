"""Wallet, loyalty, referral, subscriptions, corporate, gift hampers, share-track."""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlmodel import Session, select

from app.models.catalog import Category, Product
from app.models.engagement import (
    CorporateInquiry,
    LoyaltyAccount,
    ReferralCode,
    ShareTrackLink,
    SubscriptionPlan,
    UserSubscription,
    WalletAccount,
    WalletTxn,
)
from app.models.user import User
from app.services import orders as order_ops
from package.common.errors import AppError, BadRequestError, NotFoundError
from package.common.utils import utc_now, utc_today
from package.logger import get_logger

logger = get_logger(__name__)


def _wallet(session: Session, user_id: int) -> WalletAccount:
    row = session.exec(select(WalletAccount).where(WalletAccount.user_id == user_id)).first()
    if row:
        return row
    row = WalletAccount(user_id=user_id, balance=0)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _loyalty(session: Session, user_id: int) -> LoyaltyAccount:
    row = session.exec(select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)).first()
    if row:
        return row
    row = LoyaltyAccount(user_id=user_id, points=0, lifetime_points=0)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def wallet_summary(session: Session, user: User) -> dict:
    w = _wallet(session, user.id)
    loy = _loyalty(session, user.id)
    txns = list(
        session.exec(
            select(WalletTxn).where(WalletTxn.user_id == user.id).order_by(WalletTxn.created_at.desc()).limit(30)
        ).all()
    )
    rewards = [
        {
            "id": "free_delivery",
            "title": "Free Delivery",
            "unlock_at": 1500,
            "progress": loy.points,
            "subtitle": f"{loy.points} / 1,500 pts",
        },
        {"id": "bday", "title": "Birthday Cake Discount", "subtitle": "15% OFF · Valid once a year"},
        {"id": "refer", "title": "Refer & Earn", "subtitle": "₹100 for you & your friend"},
    ]
    return {
        "balance": w.balance,
        "loyalty_points": loy.points,
        "lifetime_points": loy.lifetime_points,
        "rewards": rewards,
        "transactions": [
            {
                "id": t.id,
                "title": t.title,
                "subtitle": t.subtitle,
                "amount": t.amount,
                "txn_type": t.txn_type,
                "balance_after": t.balance_after,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ],
    }


def wallet_add_money(session: Session, user: User, amount: float, method: str = "UPI") -> dict:
    if amount < 1 or amount > 50000:
        raise BadRequestError("Amount must be between ₹1 and ₹50,000")
    w = _wallet(session, user.id)
    w.balance = round(w.balance + amount, 2)
    w.updated_at = utc_now()
    session.add(
        WalletTxn(
            user_id=user.id,
            amount=amount,
            txn_type="credit",
            title="Added Money",
            subtitle=method,
            balance_after=w.balance,
        )
    )
    session.add(w)
    loy = _loyalty(session, user.id)
    loy.points += int(amount // 10)
    loy.lifetime_points += int(amount // 10)
    session.add(loy)
    session.commit()
    return wallet_summary(session, user)


def ensure_referral(session: Session, user: User) -> ReferralCode:
    row = session.exec(select(ReferralCode).where(ReferralCode.user_id == user.id)).first()
    if row:
        return row
    code = f"SC{user.id}{secrets.token_hex(2).upper()}"
    row = ReferralCode(user_id=user.id, code=code)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def referral_summary(session: Session, user: User) -> dict:
    ref = ensure_referral(session, user)
    return {
        "code": ref.code,
        "reward_amount": ref.reward_amount,
        "referred_count": ref.referred_count,
        "share_message": (
            f"Order fresh bakery from SweetCrust with my code {ref.code} "
            f"— we both get ₹{int(ref.reward_amount)}!"
        ),
    }


def apply_referral(session: Session, user: User, code: str) -> dict:
    code = (code or "").strip().upper()
    if not code:
        raise BadRequestError("Referral code required")
    ref = session.exec(select(ReferralCode).where(ReferralCode.code == code)).first()
    if not ref or ref.user_id == user.id:
        raise BadRequestError("Invalid referral code")
    for uid, title in ((user.id, "Referral bonus"), (ref.user_id, "Referral reward")):
        w = _wallet(session, uid)
        w.balance = round(w.balance + ref.reward_amount, 2)
        session.add(
            WalletTxn(
                user_id=uid,
                amount=ref.reward_amount,
                txn_type="credit",
                title=title,
                subtitle=f"Code {ref.code}",
                balance_after=w.balance,
            )
        )
        session.add(w)
    ref.referred_count += 1
    session.add(ref)
    session.commit()
    return {"ok": True, "credited": ref.reward_amount}


def ensure_plans(session: Session) -> list[SubscriptionPlan]:
    plans = list(session.exec(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)).all())  # noqa: E712
    if plans:
        return plans
    defaults = [
        SubscriptionPlan(name="Daily Bread Box", description="Fresh bread every morning", price=149, cadence="daily"),
        SubscriptionPlan(name="Weekend Treats", description="Pastries every Saturday", price=399, cadence="weekly"),
        SubscriptionPlan(name="Monthly Cake Club", description="1 celebration cake / month", price=899, cadence="monthly"),
    ]
    for p in defaults:
        session.add(p)
    session.commit()
    return list(session.exec(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)).all())  # noqa: E712


def list_subscriptions(session: Session, user: User) -> dict:
    plans = ensure_plans(session)
    mine = list(session.exec(select(UserSubscription).where(UserSubscription.user_id == user.id)).all())
    return {
        "plans": [
            {"id": p.id, "name": p.name, "description": p.description, "price": p.price, "cadence": p.cadence}
            for p in plans
        ],
        "mine": [
            {
                "id": s.id,
                "plan_id": s.plan_id,
                "status": s.status,
                "next_delivery_date": s.next_delivery_date.isoformat() if s.next_delivery_date else None,
            }
            for s in mine
        ],
    }


def subscribe(session: Session, user: User, plan_id: int) -> dict:
    plan = session.get(SubscriptionPlan, plan_id)
    if not plan or not plan.is_active:
        raise NotFoundError("Plan not found")
    days = 1 if plan.cadence == "daily" else 7 if plan.cadence == "weekly" else 30
    next_d = utc_today() + timedelta(days=days)
    session.add(UserSubscription(user_id=user.id, plan_id=plan_id, status="active", next_delivery_date=next_d))
    session.commit()
    return list_subscriptions(session, user)


def gift_hampers(session: Session) -> dict:
    cats = list(session.exec(select(Category).where(Category.is_active == True)).all())  # noqa: E712
    hamper_ids = {c.id for c in cats if "hamper" in (c.name or "").lower() or "gift" in (c.name or "").lower()}
    products = list(
        session.exec(select(Product).where(Product.is_active == True, Product.is_draft == False).limit(80)).all()  # noqa: E712
    )
    items = [
        p
        for p in products
        if (p.category_id in hamper_ids)
        or p.is_festival
        or "hamper" in (p.name or "").lower()
        or "gift" in (p.name or "").lower()
    ][:40]
    if not items:
        items = products[:12]
    return {"items": items, "title": "Gift Hampers", "subtitle": "Curated boxes for every occasion"}


def create_corporate(session: Session, user: User | None, body: dict) -> CorporateInquiry:
    company = (body.get("company_name") or "").strip()
    contact = (body.get("contact_name") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not company or not contact or not phone:
        raise BadRequestError("company_name, contact_name and phone are required")
    row = CorporateInquiry(
        user_id=user.id if user else None,
        company_name=company,
        contact_name=contact,
        phone=phone,
        email=body.get("email"),
        headcount=body.get("headcount"),
        occasion=body.get("occasion"),
        budget=body.get("budget"),
        notes=body.get("notes"),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def create_share_link(session: Session, user: User, order_id: int) -> dict:
    detail = order_ops.order_detail(session, order_id, user.id)
    token = secrets.token_urlsafe(16)
    link = ShareTrackLink(
        order_id=order_id,
        user_id=user.id,
        token=token,
        expires_at=utc_now() + timedelta(days=7),
    )
    session.add(link)
    session.commit()
    return {
        "token": token,
        "order_id": order_id,
        "order_number": detail["order"].order_number,
        "share_url": f"/track/share/{token}",
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


def public_track(session: Session, token: str) -> dict:
    link = session.exec(select(ShareTrackLink).where(ShareTrackLink.token == token)).first()
    if not link:
        raise NotFoundError("Tracking link not found")
    if link.expires_at and link.expires_at < utc_now():
        raise AppError("Tracking link expired", status_code=410, code="gone")
    detail = order_ops.order_detail(session, link.order_id, link.user_id)
    return {
        "order": {
            "id": detail["order"].id,
            "order_number": detail["order"].order_number,
            "status": detail["order"].status,
        },
        "tracking": detail["tracking"],
        "delivery_person": detail["delivery_person"],
        "timeline": detail["timeline"],
    }
