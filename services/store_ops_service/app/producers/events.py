"""Publish admin events via package.redis for the Fastify realtime service."""
from __future__ import annotations

from typing import Any, Optional

from package.events.topics import (
    ADMIN_EVENT,
    CHAT_MESSAGE,
    DELIVERY_LOCATION,
    ORDER_STATUS,
    USER_EVENT,
    USER_PRESENCE,
)
from package.logger import get_logger
from package.redis import redis_publish

logger = get_logger(__name__)


def emit_order_status(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(ORDER_STATUS, {**payload, "order_id": order_id}):
        logger.debug("order status broadcast skipped (redis off)")


def emit_delivery_location(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(DELIVERY_LOCATION, {**payload, "order_id": order_id}):
        logger.debug("delivery location broadcast skipped (redis off)")


def emit_chat_message(
    payload: dict[str, Any],
    *,
    conversation_id: int,
    peer_user_id: Optional[int] = None,
    sender_role: str = "",
) -> None:
    if not redis_publish(
        CHAT_MESSAGE,
        {
            **payload,
            "conversation_id": conversation_id,
            "peer_user_id": peer_user_id,
            "sender_role": sender_role,
        },
    ):
        logger.debug("chat broadcast skipped (redis off)")


def emit_presence(user_id: int, online: bool) -> None:
    if not redis_publish(USER_PRESENCE, {"user_id": user_id, "online": online}):
        logger.debug("presence broadcast skipped (redis off)")


def emit_admin_event(kind: str, payload: dict[str, Any] | None = None) -> None:
    """Instant admin console updates (shop approval, PO, etc.)."""
    if not redis_publish(ADMIN_EVENT, {"kind": kind, **(payload or {})}):
        logger.debug("admin_event skipped (redis off) kind=%s", kind)


def emit_user_event(user_id: int, kind: str, payload: dict[str, Any] | None = None) -> None:
    """Instant retailer/customer/rider updates for a single user."""
    if not redis_publish(USER_EVENT, {"user_id": int(user_id), "kind": kind, **(payload or {})}):
        logger.debug("user_event skipped (redis off) kind=%s user=%s", kind, user_id)
