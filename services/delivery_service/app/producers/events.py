"""Publish delivery events via package.redis for the Fastify realtime service."""
from __future__ import annotations

from typing import Any, Optional

from package.events.topics import ADMIN_EVENT, DELIVERY_LOCATION, ORDER_STATUS, USER_EVENT
from package.logger import get_logger
from package.redis import redis_publish

logger = get_logger(__name__)


def emit_order_status(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(ORDER_STATUS, {**payload, "order_id": order_id}):
        logger.debug("order status broadcast skipped (redis off)")


def emit_delivery_location(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(DELIVERY_LOCATION, {**payload, "order_id": order_id}):
        logger.debug("delivery location broadcast skipped (redis off)")


def emit_user_event(user_id: int, kind: str, payload: dict[str, Any] | None = None) -> None:
    if not redis_publish(USER_EVENT, {"user_id": int(user_id), "kind": kind, **(payload or {})}):
        logger.debug("user_event skipped (redis off) kind=%s user=%s", kind, user_id)


def emit_admin_event(kind: str, payload: dict[str, Any] | None = None) -> None:
    if not redis_publish(ADMIN_EVENT, {"kind": kind, **(payload or {})}):
        logger.debug("admin_event skipped (redis off) kind=%s", kind)
