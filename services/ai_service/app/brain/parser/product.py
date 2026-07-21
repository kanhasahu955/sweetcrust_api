from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class ProductEnrichOutput(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    flavor: Optional[str] = None
    weight: Optional[str] = None
    selling_price: Optional[float] = None
    original_price: Optional[float] = None
    tags: Optional[list[str]] = None
    ingredients: Optional[str] = None
    allergens: Optional[str] = None
    is_eggless: Optional[bool] = None
    filters: Optional[list[str]] = None


product_parser = PydanticOutputParser(pydantic_object=ProductEnrichOutput)


def parse_product_enrich(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        return {k: v for k, v in product_parser.parse(text).model_dump().items() if v is not None}
    except Exception:
        pass
    try:
        data = json.loads(text)
        return {k: v for k, v in ProductEnrichOutput.model_validate(data).model_dump().items() if v is not None}
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return {k: v for k, v in ProductEnrichOutput.model_validate(data).model_dump().items() if v is not None}
            except Exception:
                pass
    return {}
