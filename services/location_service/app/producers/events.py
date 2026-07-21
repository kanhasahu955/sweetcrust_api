"""Publish commerce events via package.redis for the Fastify realtime service."""
from __future__ import annotations

from typing import Any, Optional

from package.events.topics import CHAT_MESSAGE, ORDER_STATUS
from package.logger import get_logger
from package.redis import redis_publish

logger = get_logger(__name__)


def emit_order_status(order_id: int, payload: dict[str, Any]) -> None:
    if not redis_publish(ORDER_STATUS, {**payload, "order_id": order_id}):
        logger.debug("order status broadcast skipped (redis off)")


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
