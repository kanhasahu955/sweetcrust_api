"""Shared cross-service API envelopes (domain schemas stay in each service)."""

from package.common.schemas import (
    APIModel,
    DataOut,
    ErrorBody,
    HealthOut,
    MessageOut,
    fail,
    ok,
)

__all__ = [
    "APIModel",
    "ErrorBody",
    "MessageOut",
    "DataOut",
    "HealthOut",
    "ok",
    "fail",
]
