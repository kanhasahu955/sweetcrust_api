"""AI guards — package rate limit + Twilio signature."""
from __future__ import annotations

from typing import Mapping, Optional

from fastapi import Request

from app.config import get_settings
from package.common.errors import ForbiddenError, ServiceUnavailableError
from package.common.rate_limit import enforce_rate


def enforce_chat_rate(user_id: int) -> None:
    settings = get_settings()
    enforce_rate(
        f"ai:chat:{user_id}",
        limit=settings.ai_chat_rate_limit,
        window_sec=settings.ai_chat_rate_window_sec,
    )


async def assert_twilio_signature(request: Request, form: Optional[Mapping[str, str]] = None) -> dict:
    """Validate X-Twilio-Signature. Dev allows skip when auth token unset."""
    settings = get_settings()
    data = dict(form) if form is not None else {}
    if form is None:
        try:
            data = {str(k): str(v) for k, v in (await request.form()).items()}
        except Exception:
            data = {}

    if not settings.twilio_auth_token:
        if settings.is_dev:
            return data
        raise ServiceUnavailableError("Twilio is not configured")

    from twilio.request_validator import RequestValidator

    base = (settings.twilio_webhook_base_url or "").rstrip("/")
    path = request.url.path
    query = request.url.query
    url = f"{base}{path}" + (f"?{query}" if query else "")
    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.twilio_auth_token)
    if not validator.validate(url, data, signature):
        raise ForbiddenError("Invalid Twilio signature")
    return data
