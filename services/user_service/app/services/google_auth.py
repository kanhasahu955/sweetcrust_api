"""Verify Google Sign-In ID tokens — no-op when GOOGLE_CLIENT_ID missing."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import get_settings
from package.logger import get_logger

logger = get_logger(__name__)


def verify_google_id_token(id_token: str) -> Optional[dict[str, Any]]:
    settings = get_settings()
    if not settings.google_client_id:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
            if resp.status_code != 200:
                logger.warning("Google tokeninfo failed: %s", resp.text[:200])
                return None
            data = resp.json()
        if data.get("aud") != settings.google_client_id:
            if data.get("azp") != settings.google_client_id:
                logger.warning("Google token audience mismatch")
                return None
        if data.get("email_verified") in ("false", False):
            return None
        return {
            "email": data.get("email"),
            "name": data.get("name"),
            "picture": data.get("picture"),
            "sub": data.get("sub"),
        }
    except Exception:
        logger.exception("Google token verify failed")
        return None
