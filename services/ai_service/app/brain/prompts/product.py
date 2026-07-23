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

PRODUCT_COPY_SYSTEM = """You write marketplace listing copy for Indian bakery / namkeen retailers on SweetCrust (INR).
Reply with JSON only — no markdown fences.
Tone: warm, clear, trustworthy. No fake claims or medical claims.
Details MUST be point-wise (bullet lines with •), never a single marketing paragraph.
Include realistic ingredients and how the item is prepared for that product type.
"""

PRODUCT_COPY_USER = """Suggest listing copy for this product.

Product name: {name}
Category: {category}
Variation set: {variation}
Already shown (do not repeat): {exclude}

Return JSON with:
- short_descriptions: array of 5 distinct one-line blurbs (max ~90 chars each)
- details: array of 5 distinct options. EACH option is one string with point-wise sections using newlines and • bullets, in this shape:

About:
• one short line about the product
• one short line about taste/texture
Ingredients:
• ingredient 1
• ingredient 2
• ingredient 3
How it's made:
• step or method point 1
• step or method point 2
Storage:
• storage / shelf tip

Keep each details option under ~900 characters. Make variation set {variation} clearly different from already shown options.
"""

product_copy_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", PRODUCT_COPY_SYSTEM),
        ("human", PRODUCT_COPY_USER),
    ]
)

BANNER_COPY_SYSTEM = """You write short promo banner copy for Indian bakery / namkeen shop apps on SweetCrust.
Reply with JSON only — no markdown fences.
Tone: warm, clear, inviting. No fake discounts or medical claims.
Titles are punchy (max ~40 chars). Subtitles support the title (max ~70 chars).
"""

BANNER_COPY_USER = """Suggest shop banner lines.

Shop name: {shop_name}
Hint / theme: {hint}
Variation set: {variation}
Already shown (do not repeat): {exclude}

Return JSON with:
- titles: array of 5 distinct banner titles
- subtitles: array of 5 distinct supporting subtitles

Make variation set {variation} clearly different from already shown options.
"""

banner_copy_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", BANNER_COPY_SYSTEM),
        ("human", BANNER_COPY_USER),
    ]
)
