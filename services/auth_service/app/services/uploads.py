"""Local upload for pre-auth retailer KYC / logo (no AI guardrails)."""
from __future__ import annotations

import uuid
from pathlib import Path

from app.config import get_settings


def store_upload(
    *,
    content: bytes,
    purpose: str,
    filename: str,
    content_type: str | None,
) -> dict:
    purpose = (purpose or "kyc").lower()
    if purpose not in ("kyc", "shop_logo", "product"):
        return {"success": False, "detail": "purpose must be kyc, shop_logo, or product"}
    if not content:
        return {"success": False, "detail": "Empty file"}
    if len(content) > 15 * 1024 * 1024:
        return {"success": False, "detail": "Max 15MB"}
    if content_type and not content_type.startswith("image/") and content_type != "application/octet-stream":
        return {"success": False, "detail": "Upload blocked: expected image"}

    root = Path(get_settings().upload_dir)
    dest_dir = root / "sweetcrust" / "retailer" / purpose
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = f"{uuid.uuid4().hex}_{Path(filename or 'upload.jpg').name}"
    path = dest_dir / safe
    path.write_bytes(content)
    url = f"/uploads/sweetcrust/retailer/{purpose}/{safe}"
    return {"success": True, "purpose": purpose, "url": url, "provider": "local"}
