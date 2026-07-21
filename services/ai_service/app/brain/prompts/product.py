from langchain_core.prompts import ChatPromptTemplate

PRODUCT_ENRICH_SYSTEM = """You help Indian bakery owners write marketplace product copy for SweetCrust Bakery (Mumbai, INR, GST).
Reply with JSON only — no markdown fences.
Improve title, description, tags, pricing suggestions, allergens, and filters.
Keep tone premium and welcoming. Prices in Indian rupees.
"""

PRODUCT_ENRICH_USER = """Improve this bakery product draft.

Notes: {notes}
Image URLs: {image_urls}
Draft JSON:
{draft}

Return JSON with keys:
name, title, short_description, description, category, flavor, weight,
selling_price, original_price, tags, ingredients, allergens, is_eggless, filters
"""

product_enrich_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", PRODUCT_ENRICH_SYSTEM),
        ("human", PRODUCT_ENRICH_USER),
    ]
)
