"""Publish admin / order events via Redis for the Fastify realtime service."""
from __future__ import annotations

from typing import Any

from package.events.topics import ADMIN_EVENT, ORDER_STATUS
from package.logger import get_logger
from package.redis import redis_publish

logger = get_logger(__name__)


def emit_admin_event(kind: str, payload: dict[str, Any] | None = None) -> None:
    if not redis_publish(ADMIN_EVENT, {"kind": kind, **(payload or {})}):
        logger.debug("admin_event skipped (redis off) kind=%s", kind)


def emit_order_status(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(ORDER_STATUS, {**payload, "order_id": order_id}):
        logger.debug("order status broadcast skipped (redis off)")
