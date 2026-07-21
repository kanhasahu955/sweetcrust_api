"""Auth domain — ported from monolith backend/services/auth_service.py."""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlmodel import Session, select

from app.models.enums import UserRole
from app.models.ops import DeliveryPerson
from app.models.user import OTPCode, RetailerProfile, User
from app.repositories import users as users_repo
from app.services import ephemeral, presence
from app.services.google_auth import verify_google_id_token
from app.services.mail import send_admin_confirm_email, send_login_notice, send_otp_email
from app.services.sms import send_otp_sms
from app.config import get_settings
from package.common.auth import create_token_pair, decode_token
from package.common.auth.blacklist import blacklist_token
from package.common.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from package.common.utils import hash_password, utc_now, verify_password
from package.logger import get_logger
from package.redis import redis_delete, redis_get, redis_incr, redis_set

logger = get_logger(__name__)

OTP_RATE_LIMIT = 5
OTP_RATE_WINDOW_SECONDS = 600


def _normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return "+91" + digits
    if phone.startswith("+"):
        return phone
    return "+" + digits


def _otp_code() -> str:
    settings = get_settings()
    if settings.is_dev and settings.otp_dev_code:
        return settings.otp_dev_code
    return f"{secrets.randbelow(1_000_000):06d}"


def _issue_tokens(session: Session, user: User) -> dict:
    presence.set_online(session, user.id)
    if user.email:
        send_login_notice(user.email, user.name)
    tokens = create_token_pair(user.id, user.role.value)
    tokens["user"] = _user_dict(user)
    return tokens


def send_otp(session: Session, phone: str, purpose: str = "login", email: str | None = None) -> dict:
    settings = get_settings()
    phone = _normalize_phone(phone)
    rl_count = redis_incr(f"otp:rl:{phone}", OTP_RATE_WINDOW_SECONDS)
    if rl_count is not None and rl_count > OTP_RATE_LIMIT:
        raise RateLimitError("Too many OTP requests. Try again in a few minutes.")
    code = _otp_code()
    expires = utc_now() + timedelta(minutes=settings.otp_expire_minutes)

    otp = OTPCode(phone=phone, code=code, purpose=purpose, expires_at=expires)
    session.add(otp)
    session.commit()

    redis_set(f"otp:{purpose}:{phone}", code, settings.otp_expire_minutes * 60)

    if settings.is_dev:
        return {
            "phone": phone,
            "message": "OTP ready (dev — SMS/email skipped)",
            "sms_sent": False,
            "email_sent": False,
            "dev_otp": code,
        }

    sms_sent = send_otp_sms(phone, code)

    mail_sent = False
    target_email = email
    if not target_email:
        user = users_repo.get_by_phone(session, phone)
        if user and user.email:
            target_email = user.email
    if target_email:
        mail_sent = send_otp_email(target_email, code, purpose)

    if not sms_sent and not mail_sent:
        logger.warning("OTP stored but neither SMS nor email delivered for %s", phone)

    return {
        "phone": phone,
        "message": "OTP sent",
        "sms_sent": sms_sent,
        "email_sent": mail_sent,
        "dev_otp": None,
    }


def _check_otp(session: Session, phone: str, code: str, purpose: str | None = None) -> OTPCode:
    cached = redis_get(f"otp:{purpose or 'login'}:{phone}")
    if cached and cached == code:
        otp = session.exec(
            select(OTPCode)
            .where(OTPCode.phone == phone, OTPCode.code == code, OTPCode.is_used == False)  # noqa: E712
            .order_by(OTPCode.id.desc())
        ).first()
        if otp:
            return otp
        otp = OTPCode(
            phone=phone,
            code=code,
            purpose=purpose or "login",
            expires_at=utc_now() + timedelta(minutes=1),
        )
        session.add(otp)
        session.commit()
        session.refresh(otp)
        return otp

    q = select(OTPCode).where(OTPCode.phone == phone, OTPCode.is_used == False, OTPCode.code == code)  # noqa: E712
    if purpose:
        q = q.where(OTPCode.purpose == purpose)
    otp = session.exec(q.order_by(OTPCode.id.desc())).first()
    if not otp or otp.expires_at < utc_now():
        raise BadRequestError("Invalid or expired OTP")
    return otp


def verify_otp_and_login(
    session: Session,
    phone: str,
    code: str,
    name: str | None = None,
    email: str | None = None,
    terms_accepted: bool = True,
) -> dict:
    phone = _normalize_phone(phone)
    otp = _check_otp(session, phone, code)
    otp.is_used = True
    redis_delete(f"otp:login:{phone}")
    redis_delete(f"otp:{otp.purpose}:{phone}")

    user = users_repo.get_by_phone(session, phone)
    if not user:
        if not terms_accepted:
            raise BadRequestError("Accept terms and privacy policy")
        user = User(
            phone=phone,
            name=name or "Guest User",
            email=email,
            role=UserRole.CUSTOMER,
            terms_accepted=terms_accepted,
        )
        session.add(user)
    else:
        if user.role != UserRole.CUSTOMER:
            raise ForbiddenError(f"Use the {user.role.value} login endpoint for this account")
        if name:
            user.name = name
        if email:
            user.email = email
        user.terms_accepted = terms_accepted or user.terms_accepted
    session.commit()
    session.refresh(user)
    return _issue_tokens(session, user)


def google_login(session: Session, id_token: str, terms_accepted: bool = True) -> dict:
    info = verify_google_id_token(id_token)
    if not info or not info.get("email"):
        raise UnauthorizedError(
            "Invalid Google token. Use Continue with Google (browser sign-in), or check GOOGLE_CLIENT_ID."
        )
    email = info["email"]
    user = users_repo.get_by_email(session, email)
    if not user:
        if not terms_accepted:
            raise BadRequestError("Accept terms and privacy policy")
        phone = f"+91G{info['sub'][-10:]}"
        user = User(
            phone=phone,
            name=info.get("name") or email.split("@")[0],
            email=email,
            avatar_url=info.get("picture"),
            role=UserRole.CUSTOMER,
            terms_accepted=True,
        )
        session.add(user)
    else:
        if user.role != UserRole.CUSTOMER:
            raise ForbiddenError("Google login is for customers only")
        if info.get("name"):
            user.name = info["name"]
        if info.get("picture"):
            user.avatar_url = info["picture"]
    session.commit()
    session.refresh(user)
    return _issue_tokens(session, user)


def customer_google_callback_uri(_api_base: str | None = None) -> str:
    return retailer_google_callback_uri(_api_base)


def customer_google_oauth_setup(api_base: str | None = None) -> dict:
    return retailer_google_oauth_setup(api_base)


def customer_google_oauth_authorize_url(*, api_base: str, app_redirect: str) -> str:
    return _google_oauth_authorize_url(
        api_base=api_base,
        app_redirect=app_redirect,
        role="customer",
        allowed_prefixes=("usermobile:", "exp:", "http://", "https://"),
    )


def customer_google_oauth_finish(session: Session, *, code: str, state: str) -> tuple[str, dict]:
    return _google_oauth_finish(session, code=code, state=state)


def guest_login(session: Session) -> dict:
    phone = f"+91GUEST{utc_now().strftime('%H%M%S%f')[:10]}"
    user = User(phone=phone, name="Guest", role=UserRole.CUSTOMER, is_guest=True, terms_accepted=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    tokens = create_token_pair(user.id, user.role.value)
    tokens["user"] = _user_dict(user)
    return tokens


def admin_exists(session: Session) -> bool:
    return users_repo.get_admin(session) is not None


def admin_registration_status(session: Session) -> dict:
    admin = users_repo.get_admin(session)
    return {
        "admin_exists": admin is not None,
        "registration_open": admin is None,
        "email_verified": bool(admin.email_verified) if admin else False,
        "email": admin.email if admin and not admin.email_verified else None,
    }


def admin_register(session: Session, name: str, phone: str, email: str, password: str) -> dict:
    settings = get_settings()
    if admin_exists(session):
        raise ConflictError("Admin already registered. Please sign in.")
    phone = _normalize_phone(phone)
    email = email.strip().lower()
    if users_repo.get_by_phone(session, phone):
        raise BadRequestError("Phone already in use")
    if users_repo.get_by_email(session, email):
        raise BadRequestError("Email already in use")
    if len(password) < 6:
        raise BadRequestError("Password must be at least 6 characters")

    user = User(
        phone=phone,
        name=name.strip(),
        email=email,
        email_verified=False,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        terms_accepted=True,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    code = _otp_code()
    expires = utc_now() + timedelta(minutes=settings.otp_expire_minutes)
    session.add(OTPCode(phone=phone, code=code, purpose="admin_confirm", expires_at=expires))
    session.commit()
    redis_set(f"otp:admin_confirm:{phone}", code, settings.otp_expire_minutes * 60)

    mail_sent = send_admin_confirm_email(email, code, name)
    # Always return code for first-admin bootstrap — SMTP can "succeed" while Gmail drops the mail.
    return {
        "message": "Admin registered. Confirm the code sent to your email before signing in.",
        "email": email,
        "phone": phone,
        "email_sent": mail_sent,
        "dev_code": code,
    }


def admin_confirm_email(session: Session, email: str, code: str) -> dict:
    email = email.strip().lower()
    user = users_repo.get_admin_by_email(session, email)
    if not user:
        raise NotFoundError("Admin account not found")
    if user.email_verified:
        return {"message": "Email already confirmed", "email_verified": True}
    otp = _check_otp(session, user.phone, code, purpose="admin_confirm")
    otp.is_used = True
    user.email_verified = True
    session.add(user)
    session.add(otp)
    redis_delete(f"otp:admin_confirm:{user.phone}")
    session.commit()
    return {"message": "Email confirmed. You can sign in now.", "email_verified": True}


def admin_resend_confirmation(session: Session, email: str) -> dict:
    settings = get_settings()
    email = email.strip().lower()
    user = users_repo.get_admin_by_email(session, email)
    if not user:
        raise NotFoundError("Admin account not found")
    if user.email_verified:
        return {"message": "Email already confirmed", "email_sent": False}
    code = _otp_code()
    expires = utc_now() + timedelta(minutes=settings.otp_expire_minutes)
    session.add(OTPCode(phone=user.phone, code=code, purpose="admin_confirm", expires_at=expires))
    session.commit()
    redis_set(f"otp:admin_confirm:{user.phone}", code, settings.otp_expire_minutes * 60)
    mail_sent = send_admin_confirm_email(email, code, user.name)
    return {
        "message": "Confirmation code sent",
        "email_sent": mail_sent,
        "dev_code": code if settings.is_dev or not mail_sent else None,
    }


def admin_login(
    session: Session,
    password: str,
    *,
    phone: str | None = None,
    email: str | None = None,
) -> dict:
    user: User | None = None
    if phone:
        phone = _normalize_phone(phone)
        user = users_repo.get_admin_by_phone(session, phone)
    elif email:
        email = email.strip().lower()
        user = users_repo.get_admin_by_email(session, email)
    else:
        raise BadRequestError("Phone or email is required")

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")
    if not user.is_active:
        raise ForbiddenError("Account disabled")
    if not user.email_verified:
        raise ForbiddenError("Confirm your email before signing in. Check your inbox for the code.")
    return _issue_tokens(session, user)


def admin_otp_login(session: Session, phone: str, code: str) -> dict:
    phone = _normalize_phone(phone)
    user = users_repo.get_admin_by_phone(session, phone)
    if not user:
        raise ForbiddenError("Admin account not found")
    if not user.email_verified:
        raise ForbiddenError("Confirm your email before signing in")
    otp = _check_otp(session, phone, code)
    otp.is_used = True
    redis_delete(f"otp:login:{phone}")
    redis_delete(f"otp:{otp.purpose}:{phone}")
    session.commit()
    return _issue_tokens(session, user)


def _ensure_retailer_stub(session: Session, user: User) -> None:
    existing = users_repo.get_retailer_profile(session, user.id)
    if existing:
        changed = False
        if user.name and (not existing.owner_name or existing.owner_name in ("", "Shop Owner")):
            existing.owner_name = user.name
            changed = True
        if user.avatar_url and not existing.shop_logo_url:
            existing.shop_logo_url = user.avatar_url
            changed = True
        if changed:
            session.add(existing)
            session.commit()
        return
    phone = user.phone or ""
    contact = None if phone.startswith("+91R") else (phone or None)
    session.add(
        RetailerProfile(
            user_id=user.id,
            shop_name="My Shop",
            owner_name=user.name,
            contact_phone=contact,
            shop_logo_url=user.avatar_url,
            credit_allowed=False,
            credit_limit=0.0,
            outstanding_balance=0.0,
            is_blocked=False,
            approval_status="incomplete",
            is_open=True,
        )
    )
    session.commit()


def _retailer_gate_login(profile) -> None:
    status_val = getattr(profile, "approval_status", "approved") if profile else "approved"
    if status_val == "rejected":
        raise ForbiddenError("Shop registration was rejected. Contact the bakery owner.")
    if profile and profile.is_blocked:
        raise ForbiddenError("Shop is blocked")


def retailer_otp_login(
    session: Session,
    phone: str,
    code: str,
    *,
    name: str | None = None,
    terms_accepted: bool = True,
) -> dict:
    phone = _normalize_phone(phone)
    otp = _check_otp(session, phone, code)
    otp.is_used = True
    redis_delete(f"otp:login:{phone}")
    redis_delete(f"otp:{otp.purpose}:{phone}")

    user = users_repo.get_by_phone(session, phone)
    if not user:
        if not terms_accepted:
            raise BadRequestError("Accept terms and privacy policy")
        user = User(
            phone=phone,
            name=(name or "Shop Owner").strip(),
            role=UserRole.RETAILER,
            terms_accepted=True,
            is_active=True,
            is_online=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        _ensure_retailer_stub(session, user)
    else:
        if user.role != UserRole.RETAILER:
            raise ForbiddenError(f"Use the {user.role.value} login for this account")
        if name:
            user.name = name.strip()
        user.terms_accepted = terms_accepted or user.terms_accepted
        session.add(user)
        session.commit()
        session.refresh(user)
        _ensure_retailer_stub(session, user)

    profile = users_repo.get_retailer_profile(session, user.id)
    _retailer_gate_login(profile)
    return _issue_tokens(session, user)


def _retailer_google_tokens_for_info(session: Session, info: dict, *, is_new_hint: bool = False) -> dict:
    email = info["email"]
    is_new = is_new_hint
    user = users_repo.get_by_email(session, email)
    if not user:
        is_new = True
        phone = f"+91R{info['sub'][-10:]}"
        if users_repo.get_by_phone(session, phone):
            phone = f"+91R{secrets.token_hex(4)[:10]}"
        user = User(
            phone=phone,
            name=info.get("name") or email.split("@")[0],
            email=email,
            email_verified=True,
            avatar_url=info.get("picture"),
            role=UserRole.RETAILER,
            terms_accepted=True,
            is_active=True,
            is_online=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        _ensure_retailer_stub(session, user)
    else:
        if user.role != UserRole.RETAILER:
            raise ForbiddenError(
                f"This Google account is already registered as {user.role.value}. "
                "Use a different Google account for retailer sign-in."
            )
        if info.get("name"):
            user.name = info["name"]
        if info.get("picture"):
            user.avatar_url = info["picture"]
        user.email_verified = True
        session.add(user)
        session.commit()
        session.refresh(user)
        _ensure_retailer_stub(session, user)

    profile = users_repo.get_retailer_profile(session, user.id)
    _retailer_gate_login(profile)
    status_val = getattr(profile, "approval_status", "incomplete") if profile else "incomplete"
    tokens = _issue_tokens(session, user)
    tokens["is_new"] = is_new
    tokens["approval_status"] = status_val
    if is_new:
        tokens["message"] = (
            "Google registration successful. Complete your shop profile and KYC, "
            "then send for owner approval."
        )
    elif status_val == "incomplete":
        tokens["message"] = "Welcome back. Finish your shop profile to submit for approval."
    elif status_val == "pending":
        tokens["message"] = "Welcome back. Your shop is awaiting owner approval."
    else:
        tokens["message"] = "Welcome back. You are signed in with Google."
    return tokens


def retailer_google_login(session: Session, id_token: str, terms_accepted: bool = True) -> dict:
    if not terms_accepted:
        raise BadRequestError("Accept terms and privacy policy")
    info = verify_google_id_token(id_token)
    if not info or not info.get("email"):
        raise UnauthorizedError(
            "Invalid Google token. Use Continue with Google (browser sign-in), or check GOOGLE_CLIENT_ID."
        )
    return _retailer_google_tokens_for_info(session, info)


def _is_private_lan_host(url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    if host.startswith("192.168.") or host.startswith("10."):
        return True
    if host.startswith("172."):
        try:
            second = int(host.split(".")[1])
            return 16 <= second <= 31
        except (IndexError, ValueError):
            return False
    return False


def retailer_google_callback_uri(_api_base: str | None = None) -> str:
    settings = get_settings()
    # Gateway public URL (backend_v2) — not the old monolith :8000
    base = (settings.auth_public_base_url or "http://127.0.0.1:8080").rstrip("/")
    if _is_private_lan_host(base):
        base = "http://127.0.0.1:8080"
    return f"{base}/api/v1/auth/retailer/google/callback"


def retailer_google_oauth_setup(api_base: str | None = None) -> dict:
    settings = get_settings()
    callback = retailer_google_callback_uri()
    lan_warning = None
    if api_base and _is_private_lan_host(api_base):
        lan_warning = (
            "Google rejects 192.168.x.x / 10.x redirect URIs. "
            "Do NOT add your LAN IP in Console. Use localhost (simulator) or an https tunnel (phone)."
        )
    localhost_cb = callback.replace("127.0.0.1", "localhost")
    return {
        "client_id_configured": bool(settings.google_client_id),
        "client_secret_configured": bool(settings.google_client_secret),
        "auth_public_base_url": settings.auth_public_base_url,
        "request_api_base": api_base,
        "redirect_uri": callback,
        "authorized_redirect_uris_to_add": [
            callback,
            localhost_cb,
        ],
        "lan_ip_not_allowed": lan_warning,
        "phone_testing": (
            "On a physical phone, run a tunnel so Google gets a public https redirect, e.g. "
            "`npx cloudflared tunnel --url http://127.0.0.1:8080` then set AUTH_PUBLIC_BASE_URL "
            "to the https://….trycloudflare.com URL and add that …/api/v1/auth/retailer/google/callback in Console."
        ),
        "checklist": [
            "Use OAuth client type: Web application (not iOS/Android)",
            "Remove any http://192.168.… redirect URI — Google will not accept it",
            "Remove old :8000 redirect URIs if you migrated to the gateway (:8080)",
            f"Authorized redirect URIs → add: {callback}",
            f"Authorized redirect URIs → add: {localhost_cb}",
            "Authorized JavaScript origins → add: http://127.0.0.1:8080 and http://localhost:8080",
            "OAuth consent screen → Testing → add your Gmail as Test user",
            "Simulator: AUTH_PUBLIC_BASE_URL=http://127.0.0.1:8080",
            "Physical phone: use cloudflared/ngrok https URL as AUTH_PUBLIC_BASE_URL",
        ],
    }


def _google_oauth_authorize_url(
    *,
    api_base: str,
    app_redirect: str,
    role: str,
    allowed_prefixes: tuple[str, ...],
) -> str:
    from urllib.parse import urlencode

    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise ServiceUnavailableError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not configured")
    if not app_redirect.startswith(allowed_prefixes):
        raise BadRequestError("Invalid app redirect")

    state = secrets.token_urlsafe(24)
    callback = retailer_google_callback_uri()
    ephemeral.put(f"gauth:state:{state}", f"{role}\n{app_redirect}\n{callback}", 600)
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": callback,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


def _google_oauth_finish(session: Session, *, code: str, state: str) -> tuple[str, dict]:
    import json
    from urllib.parse import quote

    import httpx

    settings = get_settings()
    packed = ephemeral.pop(f"gauth:state:{state}")
    if not packed:
        packed = ephemeral.pop(f"gauth:cust:state:{state}")
    if not packed or "\n" not in packed:
        raise BadRequestError("Google sign-in expired. Try again.")

    parts = packed.split("\n")
    if len(parts) == 3:
        role, app_redirect, callback = parts
    else:
        role, app_redirect, callback = "retailer", parts[0], parts[1]

    try:
        with httpx.Client(timeout=20.0) as client:
            tok = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": callback,
                    "grant_type": "authorization_code",
                },
            )
            data = tok.json()
    except Exception as e:
        logger.exception("google token exchange failed")
        raise UnauthorizedError("Google token exchange failed") from e

    id_token = data.get("id_token")
    if not id_token:
        detail = data.get("error_description") or data.get("error") or "No id_token from Google"
        raise UnauthorizedError(f"Google sign-in failed: {detail}")

    if role == "customer":
        tokens = google_login(session, id_token, terms_accepted=True)
    else:
        tokens = retailer_google_login(session, id_token, terms_accepted=True)

    finish = secrets.token_urlsafe(18)
    ephemeral.put(f"gauth:finish:{finish}", json.dumps(tokens), 120)
    sep = "&" if "?" in app_redirect else "?"
    return f"{app_redirect}{sep}code={quote(finish)}", tokens


def retailer_google_oauth_authorize_url(*, api_base: str, app_redirect: str) -> str:
    return _google_oauth_authorize_url(
        api_base=api_base,
        app_redirect=app_redirect,
        role="retailer",
        allowed_prefixes=("sweetcrustretailer:", "exp:", "http://", "https://"),
    )


def retailer_google_oauth_finish(session: Session, *, code: str, state: str) -> tuple[str, dict]:
    return _google_oauth_finish(session, code=code, state=state)


def retailer_google_oauth_exchange(finish_code: str) -> dict:
    import json

    raw = ephemeral.pop(f"gauth:finish:{finish_code}")
    if not raw:
        raise BadRequestError("Google sign-in code expired. Try again.")
    return json.loads(raw)


def retailer_login(
    session: Session,
    phone: str,
    *,
    password: str | None = None,
    code: str | None = None,
) -> dict:
    phone = _normalize_phone(phone)
    user = session.exec(select(User).where(User.phone == phone, User.role == UserRole.RETAILER)).first()
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid retailer credentials")

    if password:
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid retailer credentials")
    elif code:
        otp = _check_otp(session, phone, code)
        otp.is_used = True
        redis_delete(f"otp:login:{phone}")
        redis_delete(f"otp:{otp.purpose}:{phone}")
        session.commit()
    else:
        raise BadRequestError("Provide password or OTP code")

    profile = users_repo.get_retailer_profile(session, user.id)
    _retailer_gate_login(profile)
    return _issue_tokens(session, user)


def get_retailer_profile(session: Session, user: User) -> dict:
    profile = users_repo.get_retailer_profile(session, user.id)
    return {
        "user": _user_dict(user),
        "profile": profile.model_dump() if profile else None,
    }


def delivery_login(
    session: Session,
    phone: str,
    *,
    password: str | None = None,
    code: str | None = None,
) -> dict:
    phone = _normalize_phone(phone)
    user = session.exec(select(User).where(User.phone == phone, User.role == UserRole.DELIVERY)).first()
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid delivery credentials")

    if password:
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid delivery credentials")
    elif code:
        otp = _check_otp(session, phone, code)
        otp.is_used = True
        redis_delete(f"otp:login:{phone}")
        redis_delete(f"otp:{otp.purpose}:{phone}")
        session.commit()
    else:
        raise BadRequestError("Provide password or OTP code")

    return _issue_tokens(session, user)


def reset_password(session: Session, phone: str, code: str, new_password: str) -> dict:
    phone = _normalize_phone(phone)
    otp = _check_otp(session, phone, code, purpose="reset")
    user = users_repo.get_by_phone(session, phone)
    if not user:
        raise NotFoundError("User not found")
    otp.is_used = True
    redis_delete(f"otp:reset:{phone}")
    user.password_hash = hash_password(new_password)
    session.add(user)
    session.commit()
    return {"message": "Password updated"}


def refresh_tokens(refresh_token: str, session: Session) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid or revoked refresh token")
    user = session.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise UnauthorizedError("User inactive")
    blacklist_token(refresh_token)
    return _issue_tokens(session, user)


def logout(
    session: Session,
    user: User,
    *,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> dict:
    if access_token:
        blacklist_token(access_token)
    if refresh_token:
        blacklist_token(refresh_token)
    presence.set_offline(session, user.id)
    return {"message": "Logged out"}


def get_delivery_profile(session: Session, user: User) -> dict:
    person = session.exec(select(DeliveryPerson).where(DeliveryPerson.user_id == user.id)).first()
    if not person:
        person = session.exec(select(DeliveryPerson).where(DeliveryPerson.phone == user.phone)).first()
        if person and not person.user_id:
            person.user_id = user.id
            session.add(person)
            session.commit()
            session.refresh(person)
    return {
        "user": _user_dict(user),
        "delivery_person": (
            {
                "id": person.id,
                "name": person.name,
                "phone": person.phone,
                "vehicle_number": person.vehicle_number,
                "is_available": person.is_available,
                "current_lat": person.current_lat,
                "current_lng": person.current_lng,
                "photo_url": person.photo_url,
            }
            if person
            else None
        ),
    }


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "name": user.name,
        "email": user.email,
        "email_verified": bool(getattr(user, "email_verified", False)),
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "language": user.language,
        "avatar_url": user.avatar_url,
        "is_guest": user.is_guest,
        "is_online": getattr(user, "is_online", False),
        "last_seen_at": user.last_seen_at.isoformat() if getattr(user, "last_seen_at", None) else None,
    }
