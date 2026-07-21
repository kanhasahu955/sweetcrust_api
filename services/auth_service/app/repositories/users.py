"""User / OTP data access."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.enums import UserRole
from app.models.user import OTPCode, RetailerProfile, User


def get_by_phone(session: Session, phone: str) -> User | None:
    return session.exec(select(User).where(User.phone == phone)).first()


def get_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()


def get_admin(session: Session) -> User | None:
    return session.exec(select(User).where(User.role == UserRole.ADMIN)).first()


def get_admin_by_phone(session: Session, phone: str) -> User | None:
    return session.exec(select(User).where(User.phone == phone, User.role == UserRole.ADMIN)).first()


def get_admin_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email, User.role == UserRole.ADMIN)).first()


def get_retailer_profile(session: Session, user_id: int) -> RetailerProfile | None:
    return session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user_id)).first()


def latest_unused_otp(session: Session, phone: str, code: str, purpose: str | None = None) -> OTPCode | None:
    q = select(OTPCode).where(OTPCode.phone == phone, OTPCode.is_used == False, OTPCode.code == code)  # noqa: E712
    if purpose:
        q = q.where(OTPCode.purpose == purpose)
    return session.exec(q.order_by(OTPCode.id.desc())).first()
