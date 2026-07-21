"""Publish delivery events via package.redis for the Fastify realtime service."""
from __future__ import annotations

from typing import Any

from package.events.topics import DELIVERY_LOCATION, ORDER_STATUS
from package.logger import get_logger
from package.redis import redis_publish

logger = get_logger(__name__)


def emit_order_status(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(ORDER_STATUS, {**payload, "order_id": order_id}):
        logger.debug("order status broadcast skipped (redis off)")


def emit_delivery_location(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(DELIVERY_LOCATION, {**payload, "order_id": order_id}):
        logger.debug("delivery location broadcast skipped (redis off)")
