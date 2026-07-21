"""AI-assisted product upload suggestions — LLM-enhanced when configured."""

from __future__ import annotations

import json
from package.logger import get_logger
from typing import Any

from app.config import get_settings

logger = get_logger(__name__)


class ProductAgent:
    def analyze(self, image_urls: list[str], notes: str | None = None) -> dict[str, Any]:
        hint = (notes or "").lower()
        if "bread" in hint:
            kind = "bread"
        elif "cookie" in hint:
            kind = "cookie"
        elif "cupcake" in hint:
            kind = "cupcake"
        elif "pastry" in hint:
            kind = "pastry"
        elif "donut" in hint or "doughnut" in hint:
            kind = "donut"
        else:
            kind = "cake"

        templates = {
            "cake": {
                "name": "Premium Chocolate Truffle Birthday Cake",
                "category": "Birthday Cakes",
                "flavor": "Chocolate Truffle",
                "weight": "1 kg",
                "selling_price": 899,
                "original_price": 1099,
                "is_eggless": True,
                "tags": ["chocolate cake", "birthday cake", "truffle cake", "eggless option"],
                "description": (
                    "Rich chocolate sponge layered with creamy chocolate ganache and finished "
                    "with premium chocolate decoration. Perfect for birthdays across Mumbai."
                ),
                "short_description": "Rich chocolate truffle cake with ganache finish",
                "ingredients": "Flour, cocoa, dark chocolate, cream, sugar, butter",
                "allergens": "Gluten, Milk, Soy",
                "preparation_time": 90,
                "shelf_life_hours": 36,
                "storage_instructions": "Keep refrigerated. Serve at room temperature.",
                "gst_rate": 5.0,
                "suggested_stock": 15,
            },
            "cupcake": {
                "name": "Assorted Buttercream Cupcakes (Box of 6)",
                "category": "Cupcakes",
                "flavor": "Assorted",
                "weight": "6 pcs",
                "selling_price": 399,
                "original_price": 449,
                "is_eggless": True,
                "tags": ["cupcakes", "party", "eggless"],
                "description": "Soft vanilla and chocolate cupcakes topped with silky buttercream.",
                "short_description": "Box of 6 colourful cupcakes",
                "ingredients": "Flour, butter, sugar, vanilla, cocoa",
                "allergens": "Gluten, Milk",
                "preparation_time": 45,
                "shelf_life_hours": 24,
                "storage_instructions": "Store cool and dry.",
                "gst_rate": 5.0,
                "suggested_stock": 30,
            },
            "bread": {
                "name": "Artisan Whole Wheat Bread",
                "category": "Bread",
                "flavor": "Whole Wheat",
                "weight": "400 g",
                "selling_price": 85,
                "original_price": 95,
                "is_eggless": True,
                "tags": ["bread", "healthy", "freshly baked"],
                "description": "Freshly baked whole wheat loaf with a soft crumb and crisp crust.",
                "short_description": "Daily fresh whole wheat bread",
                "ingredients": "Whole wheat flour, yeast, salt, olive oil",
                "allergens": "Gluten",
                "preparation_time": 120,
                "shelf_life_hours": 48,
                "storage_instructions": "Store in bread box.",
                "gst_rate": 5.0,
                "suggested_stock": 40,
            },
            "pastry": {
                "name": "Belgian Chocolate Pastry",
                "category": "Pastries",
                "flavor": "Belgian Chocolate",
                "weight": "1 pc",
                "selling_price": 129,
                "original_price": 149,
                "is_eggless": False,
                "tags": ["pastry", "chocolate"],
                "description": "Flaky pastry filled with Belgian chocolate cream.",
                "short_description": "Chocolate cream pastry",
                "ingredients": "Flour, butter, chocolate, cream, eggs",
                "allergens": "Gluten, Milk, Egg",
                "preparation_time": 30,
                "shelf_life_hours": 18,
                "storage_instructions": "Keep refrigerated.",
                "gst_rate": 5.0,
                "suggested_stock": 25,
            },
            "cookie": {
                "name": "Choco Chip Cookies (Pack of 8)",
                "category": "Cookies",
                "flavor": "Choco Chip",
                "weight": "250 g",
                "selling_price": 199,
                "original_price": 229,
                "is_eggless": True,
                "tags": ["cookies", "gift", "eggless"],
                "description": "Crispy-on-edges, chewy-centre choco chip cookies.",
                "short_description": "Classic choco chip cookies",
                "ingredients": "Flour, butter, chocolate chips, sugar",
                "allergens": "Gluten, Milk",
                "preparation_time": 40,
                "shelf_life_hours": 168,
                "storage_instructions": "Airtight container.",
                "gst_rate": 5.0,
                "suggested_stock": 50,
            },
            "donut": {
                "name": "Glazed Soft Donuts (Pack of 4)",
                "category": "Donuts",
                "flavor": "Vanilla Glaze",
                "weight": "4 pcs",
                "selling_price": 179,
                "original_price": 199,
                "is_eggless": False,
                "tags": ["donuts", "snacks"],
                "description": "Pillowy donuts with shiny vanilla glaze.",
                "short_description": "Fresh glazed donuts",
                "ingredients": "Flour, milk, yeast, sugar, eggs",
                "allergens": "Gluten, Milk, Egg",
                "preparation_time": 50,
                "shelf_life_hours": 12,
                "storage_instructions": "Best same day.",
                "gst_rate": 5.0,
                "suggested_stock": 20,
            },
        }
        base = templates[kind]
        filters = ["New arrival", "Same-day delivery"]
        if base.get("is_eggless"):
            filters.append("Eggless")
        if base["selling_price"] < 500:
            filters.append("Under ₹500")
        if kind == "cake":
            filters.extend(["Birthday", "Serves 5–10 people"])

        quality = {
            "score": 86,
            "categories": {
                "image_quality": 90,
                "product_visibility": 88,
                "background_quality": 84,
                "title_quality": 82,
                "description_quality": 85,
                "pricing_competitiveness": 80,
                "search_optimization": 86,
                "completeness": 78,
                "customer_attractiveness": 88,
            },
            "suggestions": [
                "Add one side-angle image",
                "Add allergen information",
                "Mention shelf life",
                "Add an eggless option",
                "Use a clearer product title",
                "Add a festival keyword",
            ],
        }

        result = {
            "detected_type": kind,
            "image_processing": {
                "enhanced": True,
                "background_improved": True,
                "blur_detected": False,
                "duplicates_found": 0,
                "cover_image": image_urls[0] if image_urls else None,
                "rejected": [],
                "angle_tips": ["Shoot from 45° with soft daylight", "Include a size reference plate"],
                "thumbnails": image_urls[:3],
            },
            "suggestions": {
                **base,
                "title": base["name"],
                "subcategory": base["category"],
                "keywords": base["tags"],
                "product_type": kind,
                "sugar_free": False,
                "filters": filters,
                "cross_sell": ["Chocolate Truffle Pastry", "Party Cupcakes"],
                "similar_products": ["Black Forest Cake", "Belgian Chocolate Cake"],
            },
            "quality": quality,
            "status": "awaiting_admin_review",
            "provider": "rules",
            "vision": False,
            "stub": True,
            "note": "Rules/notes-based suggestions — image pixels not analyzed yet.",
        }
        return self._enrich_with_llm(result, image_urls, notes)

    def _enrich_with_llm(self, result: dict[str, Any], image_urls: list[str], notes: str | None) -> dict[str, Any]:
        settings = get_settings()
        if not settings.llm_configured or not settings.llm_api_key:
            return result
        try:
            from app.brain.llm import get_chat_model
            from app.brain.parser.product import parse_product_enrich
            from app.brain.prompts.product import product_enrich_prompt

            messages = product_enrich_prompt.format_messages(
                notes=notes or "",
                image_urls=json.dumps(image_urls[:3]),
                draft=json.dumps(result["suggestions"]),
            )
            model = get_chat_model()
            if settings.llm_provider.lower() in ("openai", "groq"):
                try:
                    model = model.bind(response_format={"type": "json_object"})
                except Exception:
                    pass
            raw = model.invoke(messages).content
            data = parse_product_enrich(raw if isinstance(raw, str) else str(raw))
            if data:
                result["suggestions"].update(data)
            result["provider"] = f"langchain:{settings.llm_provider}"
            result["model"] = settings.llm_model
        except Exception:
            logger.exception("LLM product enrich skipped")
        return result


_agent = ProductAgent()
analyze_product_images = _agent.analyze
