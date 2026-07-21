"""Strict AI / messaging / photo guardrails for SweetCrust."""

from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.brain.prompts.guardrails import GUARDRAILS_SYSTEM_ADDON

# Back-compat alias for imports
SYSTEM_GUARDRAIL_ADDON = GUARDRAILS_SYSTEM_ADDON

ALLOWED_TOPICS = (
    "cake",
    "bakery",
    "pastry",
    "bread",
    "cookie",
    "donut",
    "cupcake",
    "order",
    "delivery",
    "payment",
    "upi",
    "refund",
    "return",
    "invoice",
    "gst",
    "eggless",
    "sugar",
    "custom",
    "flavour",
    "flavor",
    "weight",
    "cart",
    "coupon",
    "track",
    "hamper",
    "festival",
    "diwali",
    "birthday",
    "wedding",
    "sweetcrust",
    "menu",
    "stock",
    "allergen",
    "hello",
    "hi",
    "thanks",
    "help",
    "price",
    "₹",
    "rs",
    # B2B / village shop
    "shop",
    "retailer",
    "credit",
    "udhaar",
    "outstanding",
    "balance",
    "moq",
    "catalog",
    "wholesale",
    "owner",
    "callback",
    "call",
    "photo",
    "kyc",
    "aadhaar",
    "pan",
    "village",
    "dispatch",
    "stock",
    "sku",
    "deliver",
    "tomorrow",
    "today",
    "biscuit",
    "bread",
    "pak",
    "packet",
    "box",
    "qty",
    "quantity",
    "need",
    "want",
    "send",
    "please",
    "sir",
    "madam",
    "bhai",
    "bhabi",
)

BLOCKED_PATTERNS = [
    r"\b(kill|suicide|nsfw|porn|xxx|nude)\b",
    r"\b(election|politics|modi|bjp|congress)\b",
    r"\b(prescribe|diagnosis|lawsuit|attorney)\b",
    r"(ignore|bypass|jailbreak).*(instruction|prompt|system)",
    r"\b(crypto|bitcoin|forex trading)\b",
]

REFUSAL = (
    "I can only help with SweetCrust topics — products, shop orders, credit/udhaar, "
    "payments, delivery, returns, custom cakes, and invoices. "
    "Ask about your order, catalog, or say talk to owner."
)

PHOTO_ALLOWED_PURPOSES = {
    "product",
    "return",
    "custom_cake",
    "chat",
    "profile",
    "evidence",
    "kyc",
    "shop_logo",
}
PHOTO_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/jpg"}


def guardrails_enabled() -> bool:
    return get_settings().guardrails_enabled


def is_app_related(text: str) -> bool:
    t = (text or "").lower()
    if not t.strip():
        return False
    if any(re.search(p, t, re.I) for p in BLOCKED_PATTERNS):
        return False
    return any(k in t for k in ALLOWED_TOPICS)


def filter_user_message(text: str, *, mode: str = "ai") -> dict[str, Any]:
    """Pre-filter message. mode=peer → human chat (only hard blocks); mode=ai → topic gate."""
    if not guardrails_enabled():
        return {"allowed": True, "text": text}
    t = (text or "").strip()
    if not t:
        return {"allowed": False, "reply": REFUSAL, "reason": "empty"}
    if any(re.search(p, t, re.I) for p in BLOCKED_PATTERNS):
        return {"allowed": False, "reply": REFUSAL, "reason": "blocked_topic"}
    # Human↔human support chat: don't topic-gate shopkeeper slang
    if mode == "peer":
        return {"allowed": True, "text": t}
    # Allow short greetings / order refs even without bakery keywords
    if len(t) < 80 and (
        re.search(r"^(hi|hello|hey|namaste|thanks|ok|haan|yes|no|please|pls)\b", t, re.I)
        or re.fullmatch(r"\?+", t)
    ):
        return {"allowed": True, "text": t}
    if re.search(
        r"\b(SC\d{6,}|\border\b|\bcake\b|deliver|stock|credit|udhaar|₹|\d+\s*kg|\d+\s*pkt)\b",
        t,
        re.I,
    ):
        return {"allowed": True, "text": t}
    if not is_app_related(t):
        return {"allowed": False, "reply": REFUSAL, "reason": "off_topic"}
    if re.search(r"(whatsapp|telegram|personal number|call me on)\s*\+?\d", t, re.I):
        return {
            "allowed": True,
            "text": t,
            "note": "Prefer in-app chat or AI call for privacy.",
        }
    return {"allowed": True, "text": t}


def filter_ai_reply(text: str) -> str:
    if not guardrails_enabled():
        return text
    t = text or ""
    if any(re.search(p, t, re.I) for p in BLOCKED_PATTERNS):
        return REFUSAL
    return t


def validate_photo_upload(
    *,
    content_type: str | None,
    purpose: str | None,
    filename: str | None = None,
) -> dict[str, Any]:
    if not guardrails_enabled():
        return {"allowed": True}
    purpose = (purpose or "chat").lower()
    if purpose not in PHOTO_ALLOWED_PURPOSES:
        return {
            "allowed": False,
            "detail": f"Photo purpose must be one of: {', '.join(sorted(PHOTO_ALLOWED_PURPOSES))}",
        }
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct and ct not in PHOTO_ALLOWED_MIME:
        return {"allowed": False, "detail": "Only bakery-related images (JPEG/PNG/WebP) are allowed"}
    if filename:
        lower = filename.lower()
        if lower.endswith((".exe", ".apk", ".js", ".html", ".php")):
            return {"allowed": False, "detail": "File type not allowed"}
    return {"allowed": True, "purpose": purpose}
