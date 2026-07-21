"""Publish chat/order events via package.redis for the Fastify realtime service."""
from __future__ import annotations

from typing import Any, Optional

from package.events.topics import CHAT_MESSAGE, ORDER_STATUS
from package.logger import get_logger
from package.redis import redis_publish

logger = get_logger("ai.bridge")


def schedule_chat_broadcast(
    payload: dict[str, Any],
    *,
    conversation_id: int,
    peer_user_id: Optional[int] = None,
    sender_role: str = "",
) -> None:
    ok = redis_publish(
        CHAT_MESSAGE,
        {
            **payload,
            "conversation_id": conversation_id,
            "peer_user_id": peer_user_id,
            "sender_role": sender_role,
        },
    )
    if not ok:
        logger.debug("chat broadcast skipped (redis off)")


async def emit_order_update(order_id: int, payload: dict) -> None:
    redis_publish(ORDER_STATUS, {**payload, "order_id": order_id})


def message_payload(msg) -> dict[str, Any]:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "content": msg.content,
        "message_type": msg.message_type.value if hasattr(msg.message_type, "value") else msg.message_type,
        "sender_role": msg.sender_role,
        "sender_id": msg.sender_id,
        "media_url": msg.media_url,
        "is_delivered": getattr(msg, "is_delivered", False),
        "is_read": getattr(msg, "is_read", False),
        "created_at": msg.created_at.isoformat() if getattr(msg, "created_at", None) else None,
    }
