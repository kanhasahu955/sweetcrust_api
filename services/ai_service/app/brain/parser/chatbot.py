from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class ProductQuery(BaseModel):
    eggless: Optional[bool] = None
    sugar_free: Optional[bool] = None
    max_price: Optional[float] = None
    bestseller: Optional[bool] = None
    q: Optional[str] = None


class ChatbotAction(BaseModel):
    type: str
    order_id: Optional[int] = None
    product_id: Optional[int] = None


class ChatbotOutput(BaseModel):
    reply: str = ""
    actions: list[ChatbotAction] = Field(default_factory=list)
    product_query: ProductQuery = Field(default_factory=ProductQuery)


chatbot_parser = PydanticOutputParser(pydantic_object=ChatbotOutput)


def parse_chatbot_output(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        return chatbot_parser.parse(text).model_dump()
    except Exception:
        pass
    try:
        data = json.loads(text)
        return ChatbotOutput.model_validate(data).model_dump()
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return ChatbotOutput.model_validate(data).model_dump()
            except Exception:
                pass
    return {"reply": text, "actions": [], "product_query": {}}
