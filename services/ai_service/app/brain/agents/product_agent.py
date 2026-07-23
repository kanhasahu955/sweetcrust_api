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

    def suggest_copy(
        self,
        name: str,
        category: str | None = None,
        *,
        variation: int = 1,
        exclude: list[str] | None = None,
    ) -> dict[str, Any]:
        """AI listing copy from product name + category (no images required)."""
        from package.common.errors import BadRequestError

        n = (name or "").strip()
        c = (category or "").strip()
        if not n:
            raise BadRequestError("Product name is required")
        if len(n) < 2:
            raise BadRequestError("Product name must be at least 2 characters")
        if len(n) > 160:
            raise BadRequestError("Product name is too long")
        if not c:
            raise BadRequestError("Category is required")
        if len(c) > 160:
            raise BadRequestError("Category is too long")
        var = max(1, min(int(variation or 1), 20))
        skip = [str(x).strip() for x in (exclude or []) if str(x).strip()][:40]

        fallback = self._rules_copy(n, c, variation=var)
        settings = get_settings()
        if not settings.llm_configured or not settings.llm_api_key:
            return {**fallback, "provider": "rules", "stub": True, "variation": var}

        try:
            from app.brain.llm import get_chat_model
            from app.brain.parser.product import parse_product_copy
            from app.brain.prompts.product import product_copy_prompt

            messages = product_copy_prompt.format_messages(
                name=n,
                category=c,
                variation=str(var),
                exclude=json.dumps(skip[:12], ensure_ascii=False) if skip else "[]",
            )
            model = get_chat_model()
            if settings.llm_provider.lower() in ("openai", "groq"):
                try:
                    model = model.bind(response_format={"type": "json_object"})
                except Exception:
                    pass
            raw = model.invoke(messages).content
            data = parse_product_copy(raw if isinstance(raw, str) else str(raw))
            shorts = [s for s in (data.get("short_descriptions") or []) if s not in skip]
            details = [d for d in (data.get("details") or []) if d not in skip]
            if len(shorts) < 2 or len(details) < 2:
                shorts = shorts or fallback["short_descriptions"]
                details = details or fallback["details"]
                for s in fallback["short_descriptions"]:
                    if s not in shorts and s not in skip and len(shorts) < 6:
                        shorts.append(s)
                for d in fallback["details"]:
                    if d not in details and d not in skip and len(details) < 6:
                        details.append(d)
            return {
                "name": n,
                "category": c,
                "short_descriptions": shorts[:6],
                "details": details[:6],
                "variation": var,
                "provider": f"langchain:{settings.llm_provider}",
                "model": settings.llm_model,
                "stub": False,
            }
        except Exception:
            logger.exception("LLM product copy failed — using rules fallback")
            return {**fallback, "provider": "rules", "stub": True, "variation": var}

    @staticmethod
    def _rules_copy(name: str, category: str, variation: int = 1) -> dict[str, Any]:
        n, c = name, category
        v = max(1, variation)
        # ponytail: heuristic ingredients by keyword — upgrade path is always LLM when configured
        low = f"{n} {c}".lower()
        if "chakli" in low or "murukku" in low:
            ingredients = ["Besan / rice flour", "Butter or oil", "Cumin / ajwain", "Salt", "Sesame seeds"]
            method = ["Knead a soft spiced dough", "Press through chakli mould", "Deep-fry till golden and crisp"]
        elif "cake" in low:
            ingredients = ["Flour", "Sugar", "Butter / oil", "Eggs or eggless mix", "Cocoa or flavour"]
            method = ["Whip batter till smooth", "Bake in preheated oven", "Cool and finish with frosting"]
        elif "bread" in low:
            ingredients = ["Flour", "Yeast", "Water", "Salt", "Oil / butter"]
            method = ["Knead and proof the dough", "Shape loaves", "Bake till crust is golden"]
        else:
            ingredients = ["Quality base flour / mix", "Oil or ghee", "Seasoning / spices", "Salt"]
            method = ["Prepare fresh in small batches", "Cook or bake to order style", "Cool and pack for shelf"]

        def detail(tag: str, about: list[str]) -> str:
            lines = [
                "About:",
                *[f"• {x}" for x in about],
                "Ingredients:",
                *[f"• {x}" for x in ingredients],
                "How it's made:",
                *[f"• {x}" for x in method],
                "Storage:",
                "• Keep in an airtight box in a cool, dry place",
                "• Best within a few days of packing",
            ]
            return "\n".join(lines) + (f"\n• Batch tip: variation {tag}" if v > 1 else "")

        shorts = [
            f"Fresh {n} from our {c} range.",
            f"Homemade {n} — crispy, tasty, made daily.",
            f"Premium {n} perfect for snacking and gifting.",
            f"Classic {c} favourite: {n}.",
            f"{n} with authentic flavour, packed fresh.",
            f"Crunchy {n} — tea-time ready from {c}.",
        ]
        # rotate for "more"
        rot = (v - 1) % len(shorts)
        shorts = shorts[rot:] + shorts[:rot]
        details = [
            detail("A", [f"{n} from the {c} selection", "Crisp bite with homemade taste"]),
            detail("B", [f"Everyday snack: {n}", "Light seasoning, ready to serve"]),
            detail("C", [f"Festive tray favourite — {n}", "Consistent batch quality"]),
            detail("D", [f"Tea-time {n}", "Packed fresh for better crunch"]),
            detail("E", [f"Family pack style {n}", "Made with care in small batches"]),
        ]
        drot = (v - 1) % len(details)
        details = details[drot:] + details[:drot]
        return {
            "name": n,
            "category": c,
            "short_descriptions": shorts[:5],
            "details": details[:5],
            "variation": v,
        }


    def suggest_banner(
        self,
        shop_name: str,
        hint: str | None = None,
        *,
        variation: int = 1,
        exclude: list[str] | None = None,
    ) -> dict[str, Any]:
        """Promo banner title + subtitle options for Sell → Banners."""
        shop = (shop_name or "").strip() or "SweetCrust"
        h = (hint or "").strip() or "fresh bakery specials"
        var = max(1, min(int(variation or 1), 20))
        skip = [str(x).strip() for x in (exclude or []) if str(x).strip()][:40]
        fallback = self._rules_banner(shop, h, variation=var)

        settings = get_settings()
        if not settings.llm_configured or not settings.llm_api_key:
            return {**fallback, "provider": "rules", "stub": True, "variation": var}

        try:
            from app.brain.llm import get_chat_model
            from app.brain.parser.product import parse_banner_copy
            from app.brain.prompts.product import banner_copy_prompt

            messages = banner_copy_prompt.format_messages(
                shop_name=shop,
                hint=h,
                variation=str(var),
                exclude=json.dumps(skip[:12], ensure_ascii=False) if skip else "[]",
            )
            model = get_chat_model()
            if settings.llm_provider.lower() in ("openai", "groq"):
                try:
                    model = model.bind(response_format={"type": "json_object"})
                except Exception:
                    pass
            raw = model.invoke(messages).content
            data = parse_banner_copy(raw if isinstance(raw, str) else str(raw))
            titles = [t for t in (data.get("titles") or []) if t not in skip]
            subs = [s for s in (data.get("subtitles") or []) if s not in skip]
            if len(titles) < 2 or len(subs) < 2:
                titles = titles or fallback["titles"]
                subs = subs or fallback["subtitles"]
                for t in fallback["titles"]:
                    if t not in titles and t not in skip and len(titles) < 6:
                        titles.append(t)
                for s in fallback["subtitles"]:
                    if s not in subs and s not in skip and len(subs) < 6:
                        subs.append(s)
            return {
                "shop_name": shop,
                "hint": h,
                "titles": titles[:6],
                "subtitles": subs[:6],
                "variation": var,
                "provider": f"langchain:{settings.llm_provider}",
                "model": settings.llm_model,
                "stub": False,
            }
        except Exception:
            logger.exception("LLM banner copy failed — using rules fallback")
            return {**fallback, "provider": "rules", "stub": True, "variation": var}

    @staticmethod
    def _rules_banner(shop: str, hint: str, variation: int = 1) -> dict[str, Any]:
        v = max(1, variation)
        titles = [
            f"Fresh at {shop}",
            "Today's warm specials",
            f"{hint[:28]}" if len(hint) >= 4 else "Bakery favourites",
            "Crisp · ready now",
            "Weekend treat tray",
            "Taste of home, packed fresh",
        ]
        subs = [
            "Order for pickup or delivery",
            "Small-batch bakery favourites",
            f"From {shop} — made with care",
            "Limited trays · order early",
            "Perfect with chai this evening",
            "Tap to explore today's menu",
        ]
        rot = (v - 1) % len(titles)
        titles = titles[rot:] + titles[:rot]
        subs = subs[rot:] + subs[:rot]
        return {
            "shop_name": shop,
            "hint": hint,
            "titles": titles[:5],
            "subtitles": subs[:5],
            "variation": v,
        }


_agent = ProductAgent()
analyze_product_images = _agent.analyze
suggest_product_copy = _agent.suggest_copy
suggest_banner_copy = _agent.suggest_banner
