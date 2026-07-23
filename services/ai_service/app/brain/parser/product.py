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


class ProductCopyOutput(BaseModel):
    short_descriptions: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


def _clean_str_list(items: Any, limit: int) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def parse_product_copy(raw: str) -> dict[str, list[str]]:
    text = (raw or "").strip()
    data: Any = None
    for candidate in (text,):
        try:
            data = json.loads(candidate)
            break
        except Exception:
            pass
    if data is None:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return {"short_descriptions": [], "details": []}
    return {
        "short_descriptions": _clean_str_list(data.get("short_descriptions"), 6),
        "details": _clean_str_list(data.get("details"), 6),
    }


def parse_banner_copy(raw: str) -> dict[str, list[str]]:
    text = (raw or "").strip()
    data: Any = None
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return {"titles": [], "subtitles": []}
    return {
        "titles": _clean_str_list(data.get("titles"), 6),
        "subtitles": _clean_str_list(data.get("subtitles"), 6),
    }
