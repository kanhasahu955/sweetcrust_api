"""Razorpay Orders / Payment Links / verify / refund — httpx only (no SDK)."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Optional

import httpx

from app.config import get_settings
from package.common.errors import BadGatewayError, ServiceUnavailableError
from package.logger import get_logger

logger = get_logger(__name__)

API = "https://api.razorpay.com/v1"


def _auth() -> tuple[str, str]:
    s = get_settings()
    if not s.razorpay_configured:
        raise ServiceUnavailableError("Razorpay not configured (set RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET)")
    return s.razorpay_key_id or "", s.razorpay_key_secret or ""


def check_credentials() -> dict[str, Any]:
    s = get_settings()
    if not s.razorpay_configured:
        return {"ok": False, "configured": False, "detail": "Missing RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET"}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{API}/payments", params={"count": 1}, auth=_auth())
        if resp.status_code == 401:
            return {"ok": False, "configured": True, "detail": "Invalid Razorpay credentials (401)"}
        if resp.status_code >= 400:
            return {"ok": False, "configured": True, "detail": f"Razorpay API error {resp.status_code}"}
        mode = "test" if (s.razorpay_key_id or "").startswith("rzp_test") else "live"
        return {
            "ok": True,
            "configured": True,
            "mode": mode,
            "key_id_prefix": (s.razorpay_key_id or "")[:12] + "…",
            "webhook_configured": bool(s.razorpay_webhook_secret),
        }
    except Exception as exc:
        logger.exception("Razorpay credential check failed")
        return {"ok": False, "configured": True, "detail": str(exc)}


def check_imagekit_credentials() -> dict[str, Any]:
    s = get_settings()
    if not s.imagekit_configured:
        return {
            "ok": False,
            "configured": False,
            "detail": "Missing IMAGEKIT_PUBLIC_KEY, IMAGEKIT_PRIVATE_KEY, or IMAGEKIT_URL_ENDPOINT",
            "provider": "local",
        }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://api.imagekit.io/v1/files",
                params={"limit": 1},
                auth=(s.imagekit_private_key or "", ""),
            )
        if resp.status_code == 401:
            return {"ok": False, "configured": True, "detail": "Invalid ImageKit credentials (401)", "provider": "imagekit"}
        if resp.status_code >= 400:
            return {
                "ok": False,
                "configured": True,
                "detail": f"ImageKit API error {resp.status_code}",
                "provider": "imagekit",
            }
        return {
            "ok": True,
            "configured": True,
            "provider": "imagekit",
            "url_endpoint": s.imagekit_url_endpoint,
            "public_key_prefix": (s.imagekit_public_key or "")[:16] + "…",
        }
    except Exception as exc:
        logger.exception("ImageKit credential check failed")
        return {"ok": False, "configured": True, "detail": str(exc), "provider": "imagekit"}


def create_order(*, amount_inr: float, receipt: str, notes: Optional[dict] = None) -> dict:
    paise = max(100, int(round(float(amount_inr) * 100)))
    body = {
        "amount": paise,
        "currency": "INR",
        "receipt": receipt[:40],
        "notes": notes or {},
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{API}/orders", json=body, auth=_auth())
    if resp.status_code >= 400:
        logger.error("Razorpay create order failed: %s", resp.text)
        raise BadGatewayError(f"Razorpay order failed: {resp.text[:200]}")
    data = resp.json()
    s = get_settings()
    return {
        "razorpay_order_id": data["id"],
        "amount": data["amount"],
        "currency": data.get("currency", "INR"),
        "key_id": s.razorpay_key_id,
        "receipt": data.get("receipt"),
        "status": data.get("status"),
    }


def create_payment_link(
    *,
    amount_inr: float,
    description: str,
    reference_id: str,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    callback_url: str | None = None,
    notes: Optional[dict] = None,
) -> dict:
    paise = max(100, int(round(float(amount_inr) * 100)))
    body: dict[str, Any] = {
        "amount": paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description[:2048],
        "reference_id": reference_id[:40],
        "reminder_enable": False,
        "notes": notes or {},
    }
    customer: dict[str, str] = {}
    if customer_name:
        customer["name"] = customer_name[:50]
    if customer_phone:
        phone = customer_phone.replace("+", "").replace(" ", "")[-15:]
        if phone:
            customer["contact"] = phone
    if customer:
        body["customer"] = customer
    if callback_url:
        body["callback_url"] = callback_url
        body["callback_method"] = "get"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{API}/payment_links", json=body, auth=_auth())
    if resp.status_code >= 400:
        logger.error("Razorpay payment link failed: %s", resp.text)
        raise BadGatewayError(f"Razorpay payment link failed: {resp.text[:200]}")
    data = resp.json()
    return {
        "payment_link_id": data.get("id"),
        "short_url": data.get("short_url"),
        "amount": data.get("amount"),
        "status": data.get("status"),
        "reference_id": data.get("reference_id"),
    }


def verify_payment_signature(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    s = get_settings()
    if not s.razorpay_key_secret:
        return False
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    expected = hmac.new(s.razorpay_key_secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    s = get_settings()
    if not s.razorpay_webhook_secret:
        return False
    expected = hmac.new(s.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def refund_payment(payment_id: str, amount_inr: float | None = None) -> dict:
    body: dict[str, Any] = {}
    if amount_inr is not None:
        body["amount"] = max(100, int(round(float(amount_inr) * 100)))
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{API}/payments/{payment_id}/refund", json=body, auth=_auth())
    if resp.status_code >= 400:
        raise BadGatewayError(f"Razorpay refund failed: {resp.text[:200]}")
    return resp.json()
