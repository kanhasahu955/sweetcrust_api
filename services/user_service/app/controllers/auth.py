"""Auth controllers — shape HTTP input → domain services."""
from __future__ import annotations

import base64
import binascii

from sqlmodel import Session

from app.models.user import User
from app.services import auth as auth_svc
from app.services.uploads import store_upload
from package.common.errors import BadRequestError


def send_otp(session: Session, phone: str, purpose: str, email: str | None):
    return auth_svc.send_otp(session, phone, purpose, email)


def verify_otp(session: Session, phone: str, code: str, name, email, terms_accepted: bool):
    return auth_svc.verify_otp_and_login(session, phone, code, name, email, terms_accepted)


def google_login(session: Session, id_token: str, terms_accepted: bool):
    return auth_svc.google_login(session, id_token, terms_accepted)


def guest_login(session: Session):
    return auth_svc.guest_login(session)


def admin_registration_status(session: Session):
    return auth_svc.admin_registration_status(session)


def admin_register(session: Session, name: str, phone: str, email: str, password: str):
    return auth_svc.admin_register(session, name, phone, email, password)


def admin_confirm_email(session: Session, email: str, code: str):
    return auth_svc.admin_confirm_email(session, email, code)


def admin_resend_confirmation(session: Session, email: str):
    return auth_svc.admin_resend_confirmation(session, email)


def admin_login(session: Session, password: str, phone=None, email=None):
    return auth_svc.admin_login(session, password, phone=phone, email=email)


def admin_otp_login(session: Session, phone: str, code: str):
    return auth_svc.admin_otp_login(session, phone, code)


def delivery_login(session: Session, phone: str, password=None, code=None):
    return auth_svc.delivery_login(session, phone, password=password, code=code)


def retailer_upload(content: bytes, purpose: str, filename: str, content_type):
    return store_upload(content=content, purpose=purpose, filename=filename, content_type=content_type)


def retailer_upload_base64(content_base64: str, purpose: str, filename: str | None, content_type: str | None):
    raw = content_base64.strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        content = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise BadRequestError("Invalid base64 image data") from exc
    result = store_upload(
        content=content,
        purpose=purpose,
        filename=filename or "photo.jpg",
        content_type=content_type or "image/jpeg",
    )
    if not result.get("success"):
        raise BadRequestError(result.get("detail") or "Upload failed")
    return result


def retailer_otp_login(session, phone, code, name, terms_accepted):
    return auth_svc.retailer_otp_login(session, phone, code, name=name, terms_accepted=terms_accepted)


def retailer_google_login(session, id_token, terms_accepted):
    return auth_svc.retailer_google_login(session, id_token, terms_accepted)


def retailer_login(session, phone, password=None, code=None):
    return auth_svc.retailer_login(session, phone, password=password, code=code)


def reset_password(session, phone, code, new_password):
    return auth_svc.reset_password(session, phone, code, new_password)


def refresh_tokens(refresh_token: str, session: Session):
    return auth_svc.refresh_tokens(refresh_token, session)


def logout(session, user: User, access_token=None, refresh_token=None):
    return auth_svc.logout(session, user, access_token=access_token, refresh_token=refresh_token)


def me(user: User):
    return auth_svc._user_dict(user)


def update_me(session: Session, user: User, data: dict):
    for k, v in data.items():
        setattr(user, k, v)
    session.add(user)
    session.commit()
    session.refresh(user)
    return auth_svc._user_dict(user)
