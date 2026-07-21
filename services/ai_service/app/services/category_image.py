"""Real category cover images via OpenAI (+ ImageKit host for a durable URL)."""

from __future__ import annotations

import base64
import re
from typing import Any

import httpx
from openai import OpenAI

from app.config import get_settings
from package.common.errors import AppError
from package.common.utils.helpers import slugify
from package.logger import get_logger

logger = get_logger(__name__)


def _prompt(name: str) -> str:
    return (
        f"Professional food photography of Indian {name} for a premium bakery "
        "and village grocery catalog cover. Appetizing arrangement, warm natural "
        "light, soft cream background, shallow depth of field, no text, no watermark, "
        "no logos, no labels, photorealistic."
    )


def _host_on_imagekit(content: bytes, filename: str) -> str | None:
    settings = get_settings()
    private = getattr(settings, "imagekit_private_key", None)
    if not private:
        return None
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://upload.imagekit.io/api/v1/files/upload",
            files={
                "file": (filename, content, "image/png"),
                "fileName": (None, filename),
                "folder": (None, "/sweetcrust/categories"),
                "useUniqueFileName": (None, "true"),
            },
            auth=(private, ""),
        )
    if resp.status_code >= 400:
        logger.warning("ImageKit upload failed: %s %s", resp.status_code, resp.text[:200])
        return None
    url = resp.json().get("url")
    return str(url) if url else None


def generate_category_image(name: str) -> dict[str, Any]:
    settings = get_settings()
    clean = re.sub(r"\s+", " ", (name or "Bakery").strip()) or "Bakery"
    prompt = _prompt(clean)

    if not settings.openai_api_key:
        raise AppError(
            "OPENAI_API_KEY is not configured — cannot generate real category images.",
            code="ai_not_configured",
            status_code=503,
        )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        # Account has gpt-image-* (b64). dall-e-3 is often unavailable on newer keys.
        model = getattr(settings, "openai_image_model", None) or "gpt-image-1"
        result = client.images.generate(
            model=model,
            prompt=prompt,
            size="1024x1024",
            n=1,
        )
        item = result.data[0]
        temp_url = getattr(item, "url", None)
        b64 = getattr(item, "b64_json", None)
        revised = getattr(item, "revised_prompt", None) or prompt

        content: bytes | None = None
        if b64:
            content = base64.b64decode(b64)
        elif temp_url:
            with httpx.Client(timeout=60.0) as http:
                img = http.get(temp_url)
                img.raise_for_status()
                content = img.content
        else:
            raise AppError("OpenAI returned no image payload.", code="ai_empty", status_code=502)

        filename = f"cat-{slugify(clean)}.png"
        hosted = _host_on_imagekit(content, filename)
        if hosted:
            return {
                "stub": False,
                "image_url": hosted,
                "prompt_used": revised,
                "provider": "openai+imagekit",
            }

        if temp_url:
            return {
                "stub": False,
                "image_url": temp_url,
                "prompt_used": revised,
                "provider": "openai",
                "note": "Temporary OpenAI URL — click Add soon, or fix ImageKit hosting.",
            }

        # gpt-image returns b64 only — ImageKit is required for a browser URL
        raise AppError(
            "Image generated but ImageKit upload failed. Check IMAGEKIT_PRIVATE_KEY.",
            code="imagekit_required",
            status_code=503,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Category image generation failed")
        raise AppError(
            f"Image generation failed: {exc}",
            code="ai_image_failed",
            status_code=502,
        ) from exc
