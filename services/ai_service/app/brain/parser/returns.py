from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class ReturnAssessOutput(BaseModel):
    confidence: float = 0.5
    findings: list[str] = Field(default_factory=list)
    recommendation: Literal[
        "approve_refund", "approve_replacement", "request_more_images", "reject"
    ] = "request_more_images"
    note: str = "AI recommendation only — admin makes the final decision."
    duplicate_claim_risk: Literal["low", "medium", "high"] = "low"


return_parser = PydanticOutputParser(pydantic_object=ReturnAssessOutput)


def parse_return_assess(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        return return_parser.parse(text).model_dump()
    except Exception:
        pass
    try:
        return ReturnAssessOutput.model_validate(json.loads(text)).model_dump()
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return ReturnAssessOutput.model_validate(json.loads(m.group(0))).model_dump()
            except Exception:
                pass
    return ReturnAssessOutput().model_dump()
