"""Product vision suggestions for retailer / admin upload flows."""
from __future__ import annotations

from package.common.errors import BadRequestError


def ai_suggest_product(image_urls: list[str], notes: str | None = None) -> dict:
    from app.brain.agents.product_agent import analyze_product_images

    if not image_urls:
        raise BadRequestError("Upload at least one product photo")
    return analyze_product_images(image_urls, notes)
