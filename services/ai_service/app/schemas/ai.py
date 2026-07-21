"""Request/response DTOs owned by the AI service (base = package APIModel)."""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from package.common.schemas import APIModel


class AIChatIn(APIModel):
    message: str
    conversation_id: Optional[int] = None
    voice: bool = False
    language: str = "en"


class CallStartIn(APIModel):
    callee_id: Optional[int] = None
    order_id: Optional[int] = None
    call_type: str = "internet_audio"
    target: str = "bakery"


class CallUpdateIn(APIModel):
    status: str
    notes: Optional[str] = None
    duration_seconds: Optional[int] = None


class FAQIn(APIModel):
    question: str
    answer: str
    language: str = "en"
    is_active: bool = True


class AIProductUploadIn(APIModel):
    image_urls: list[str]
    notes: Optional[str] = None


class InsightsQuery(APIModel):
    use_llm: bool = False


class ReturnAssessIn(APIModel):
    issue_type: str
    evidence_urls: list[str] = Field(default_factory=list)
    description: Optional[str] = None
