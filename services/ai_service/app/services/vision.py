"""Product vision suggestions for retailer / admin upload flows."""
from __future__ import annotations

from package.common.errors import BadRequestError


def ai_suggest_product(image_urls: list[str], notes: str | None = None) -> dict:
    from app.brain.agents.product_agent import analyze_product_images

    if not image_urls:
        raise BadRequestError("Upload at least one product photo")
    return analyze_product_images(image_urls, notes)


def ai_suggest_product_copy(
    name: str,
    category: str | None = None,
    *,
    variation: int = 1,
    exclude: list[str] | None = None,
) -> dict:
    from package.common.errors import BadRequestError
    from app.brain.agents.product_agent import suggest_product_copy

    if not (name or "").strip():
        raise BadRequestError("Product name is required")
    if not (category or "").strip():
        raise BadRequestError("Category is required")
    return suggest_product_copy(name, category, variation=variation, exclude=exclude)


def ai_suggest_banner_copy(
    shop_name: str | None = None,
    hint: str | None = None,
    *,
    variation: int = 1,
    exclude: list[str] | None = None,
) -> dict:
    from app.brain.agents.product_agent import suggest_banner_copy

    return suggest_banner_copy(
        shop_name or "SweetCrust",
        hint,
        variation=variation,
        exclude=exclude,
    )
