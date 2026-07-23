"""Food cover images via OpenAI (+ ImageKit host for a durable URL)."""

from __future__ import annotations

import base64
import re
from typing import Any

import httpx
from openai import OpenAI

from app.config import get_settings
from package.common.errors import AppError, BadRequestError
from package.common.utils.helpers import slugify
from package.logger import get_logger

logger = get_logger(__name__)


def _clean(s: str, fallback: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()) or fallback


def _category_prompt(name: str) -> str:
    return (
        f"Professional food photography of Indian {name} for a premium bakery "
        "and village grocery catalog cover. Appetizing arrangement, warm natural "
        "light, soft cream background, shallow depth of field, no text, no watermark, "
        "no logos, no labels, photorealistic."
    )


def _product_prompt(name: str, category: str) -> str:
    return (
        f"Professional product photo of {name} from the {category} range for an Indian "
        "bakery / namkeen marketplace listing. Single hero product, appetizing, warm "
        "natural light, soft cream background, shallow depth of field, no text, no "
        "watermark, no logos, no price tags, photorealistic, square composition."
    )


def _host_on_imagekit(content: bytes, filename: str, folder: str) -> str | None:
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
                "folder": (None, folder),
                "useUniqueFileName": (None, "true"),
            },
            auth=(private, ""),
        )
    if resp.status_code >= 400:
        logger.warning("ImageKit upload failed: %s %s", resp.status_code, resp.text[:200])
        return None
    url = resp.json().get("url")
    return str(url) if url else None


def _friendly_image_error(exc: Exception) -> AppError:
    """Map OpenAI/provider noise into a short retailer-facing message."""
    text = str(exc).lower()
    if any(
        s in text
        for s in (
            "billing hard limit",
            "billing_limit",
            "insufficient_quota",
            "exceeded your current quota",
            "quota",
        )
    ):
        return AppError(
            "AI image credits ran out. Add OpenAI billing credits or raise the usage limit, then try again.",
            code="ai_billing_limit",
            status_code=502,
        )
    if "rate limit" in text or "rate_limit" in text:
        return AppError(
            "AI is busy right now. Wait a moment and try again.",
            code="ai_rate_limited",
            status_code=429,
        )
    if "content_policy" in text or "safety" in text:
        return AppError(
            "That product name couldn't be turned into an image. Try a simpler name.",
            code="ai_content_policy",
            status_code=400,
        )
    if "api key" in text or "authentication" in text or "unauthorized" in text:
        return AppError(
            "AI image is not configured correctly. Ask the owner to check OPENAI_API_KEY.",
            code="ai_auth_failed",
            status_code=503,
        )
    return AppError(
        "Couldn't generate the product image. Try again or upload a photo.",
        code="ai_image_failed",
        status_code=502,
    )


def _generate_food_image(*, name: str, prompt: str, folder: str, file_prefix: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise AppError(
            "OPENAI_API_KEY is not configured — cannot generate images.",
            code="ai_not_configured",
            status_code=503,
        )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
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

        filename = f"{file_prefix}-{slugify(name)}.png"
        hosted = _host_on_imagekit(content, filename, folder)
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
                "note": "Temporary OpenAI URL — save soon, or fix ImageKit hosting.",
            }

        raise AppError(
            "Image generated but ImageKit upload failed. Check IMAGEKIT_PRIVATE_KEY.",
            code="imagekit_required",
            status_code=503,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Food image generation failed")
        raise _friendly_image_error(exc) from exc


def generate_category_image(name: str) -> dict[str, Any]:
    clean = _clean(name, "Bakery")
    return _generate_food_image(
        name=clean,
        prompt=_category_prompt(clean),
        folder="/sweetcrust/categories",
        file_prefix="cat",
    )


def generate_product_image(name: str, category: str) -> dict[str, Any]:
    n = _clean(name, "")
    c = _clean(category, "")
    if not n or len(n) < 2:
        raise BadRequestError("Product name is required")
    if not c:
        raise BadRequestError("Category is required")
    return _generate_food_image(
        name=n,
        prompt=_product_prompt(n, c),
        folder="/sweetcrust/products",
        file_prefix="prod",
    )


if __name__ == "__main__":
    # ponytail: maps provider errors without hitting OpenAI
    assert _friendly_image_error(Exception("Billing hard limit has been reached.")).code == "ai_billing_limit"
    assert _friendly_image_error(Exception("rate_limit exceeded")).code == "ai_rate_limited"
    assert _friendly_image_error(Exception("mystery")).code == "ai_image_failed"
    print("category_image ok")
