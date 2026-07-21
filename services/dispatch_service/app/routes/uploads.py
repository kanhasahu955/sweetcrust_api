"""Local upload fallback (ImageKit stays in monolith / payments later)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.deps import CurrentUser
from app.services import integrations as integ
from app.config import get_settings
from package.common.errors import BadRequestError
from package.common.rate_limit import enforce_rate
from package.common.schemas import ok
from package.logger import get_logger

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = get_logger(__name__)


@router.get("/status")
def upload_status():
    s = get_settings()
    return ok({"provider": "imagekit" if s.imagekit_configured else "local", "imagekit_configured": s.imagekit_configured})


@router.get("/credentials/check")
def credentials_check():
    return ok(integ.check_imagekit())


@router.post("")
async def upload(
    user: CurrentUser,
    file: UploadFile = File(...),
    folder: str = Form("sweetcrust"),
    purpose: str = Form("chat"),
):
    enforce_rate(f"upload:{user.id}", limit=60, window_sec=3600)
    content = await file.read()
    if not content:
        raise BadRequestError("Empty file")
    if len(content) > 15 * 1024 * 1024:
        raise BadRequestError("Max 15MB")
    root = Path(get_settings().upload_dir)
    dest_dir = root / folder / purpose
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = file.filename or "upload.bin"
    safe = f"{uuid.uuid4().hex}_{Path(name).name}"
    path = dest_dir / safe
    path.write_bytes(content)
    url = f"/uploads/{folder}/{purpose}/{safe}"
    logger.info("upload user=%s purpose=%s bytes=%s", user.id, purpose, len(content))
    return ok({"user_id": user.id, "purpose": purpose, "url": url, "provider": "local"})
