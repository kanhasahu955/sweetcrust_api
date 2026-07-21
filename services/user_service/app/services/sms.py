"""MSG91 OTP SMS — no-op when keys missing."""
from __future__ import annotations

import httpx

from app.config import get_settings
from package.logger import get_logger

logger = get_logger(__name__)


def _digits_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return "91" + digits
    if digits.startswith("91") and len(digits) >= 12:
        return digits
    return digits


def send_otp_sms(phone: str, code: str) -> bool:
    settings = get_settings()
    if settings.is_dev and not settings.msg91_configured:
        return False
    if not settings.msg91_configured:
        logger.warning("MSG91 not configured — skip SMS to %s", phone)
        return False

    mobile = _digits_phone(phone)
    url = "https://control.msg91.com/api/v5/flow/"
    payload = {
        "template_id": settings.msg91_template_id,
        "short_url": "0",
        "recipients": [{"mobiles": mobile, "otp": code, "VAR1": code}],
    }
    headers = {
        "authkey": settings.msg91_auth_key or "",
        "Content-Type": "application/json",
        "accept": "application/json",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("MSG91 error %s: %s", resp.status_code, resp.text[:300])
            return False
        logger.info("MSG91 OTP sent to %s", mobile[-4:].rjust(len(mobile), "*"))
        return True
    except Exception:
        logger.exception("MSG91 send failed")
        return False
