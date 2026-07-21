"""Shared API request / response envelopes (per-service DTOs stay in services)."""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIModel(BaseModel):
    model_config = {"extra": "ignore"}


class ErrorBody(APIModel):
    success: bool = False
    code: str = "error"
    detail: Any = None
    request_id: Optional[str] = None


class MessageOut(APIModel):
    success: bool = True
    message: str


class DataOut(APIModel, Generic[T]):
    success: bool = True
    data: T


class HealthOut(APIModel):
    service: str
    ok: bool
    database: bool = False
    redis: bool = False
    status: str = "unknown"
    details: dict[str, Any] = Field(default_factory=dict)


def ok(data: Any = None, *, message: Optional[str] = None) -> dict:
    body: dict[str, Any] = {"success": True}
    if message is not None:
        body["message"] = message
    if data is not None:
        body["data"] = data
    return body


def fail(detail: Any, *, code: str = "error", request_id: Optional[str] = None) -> dict:
    return {
        "success": False,
        "code": code,
        "detail": detail,
        "request_id": request_id,
    }
