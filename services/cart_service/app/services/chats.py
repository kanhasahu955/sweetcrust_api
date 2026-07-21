"""Human customer chat — port of monolith chat_service (no AI guardrails)."""
from __future__ import annotations

from sqlmodel import Session, select

from app.producers.events import emit_chat_message
from app.models.enums import ChatCategory, MessageType, UserRole
from app.models.ops import ChatMessage, Conversation
from app.models.user import User
from app.services.notifications import notify
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def _first_admin(session: Session) -> User | None:
    return session.exec(select(User).where(User.role == UserRole.ADMIN)).first()


def create_conversation(session: Session, customer_id: int, data) -> Conversation:
    cat = data.category
    if hasattr(cat, "value"):
        cat = cat.value
    cat = str(cat or "general").strip().lower()
    try:
        category = ChatCategory(cat)
    except ValueError:
        category = ChatCategory.GENERAL
    conv = Conversation(
        category=category,
        customer_id=customer_id,
        order_id=getattr(data, "order_id", None),
        return_id=getattr(data, "return_id", None),
        custom_cake_id=getattr(data, "custom_cake_id", None),
        is_ai=bool(getattr(data, "is_ai", False)),
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)
    if getattr(data, "initial_message", None):
        send_message(session, conv.id, customer_id, "customer", data.initial_message)
    return conv


def list_conversations(session: Session, user: User) -> list[dict]:
    rows = list(
        session.exec(
            select(Conversation)
            .where(Conversation.customer_id == user.id)
            .order_by(Conversation.updated_at.desc())
        ).all()
    )
    return [_conversation_dict(session, c) for c in rows]


def _conversation_dict(session: Session, conv: Conversation) -> dict:
    peer = session.get(User, conv.customer_id)
    admin = session.get(User, conv.admin_id) if conv.admin_id else _first_admin(session)
    cat = conv.category.value if hasattr(conv.category, "value") else str(conv.category)
    return {
        "id": conv.id,
        "category": cat,
        "customer_id": conv.customer_id,
        "participant_id": conv.customer_id,
        "participant_role": "customer",
        "participant_name": (peer.name if peer else None) or (peer.phone if peer else "User"),
        "participant_phone": peer.phone if peer else None,
        "participant_online": bool(getattr(peer, "is_online", False)) if peer else False,
        "participant_last_seen_at": peer.last_seen_at.isoformat() if peer and peer.last_seen_at else None,
        "admin_id": conv.admin_id or (admin.id if admin else None),
        "admin_online": bool(getattr(admin, "is_online", False)) if admin else False,
        "admin_name": (admin.name if admin else None) or "SweetCrust",
        "is_ai": conv.is_ai,
        "ai_handed_over": conv.ai_handed_over,
        "last_message": conv.last_message,
        "unread_customer": conv.unread_customer,
        "unread_admin": conv.unread_admin,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


def send_message(
    session: Session,
    conversation_id: int,
    sender_id: int | None,
    sender_role: str,
    content: str | None = None,
    message_type: str = "text",
    media_url: str | None = None,
    metadata_json: dict | None = None,
) -> ChatMessage:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    if sender_role == "customer" and not content and message_type == "text" and not media_url:
        raise BadRequestError("Message content required")

    peer = session.get(User, conv.customer_id)
    admin = _first_admin(session)
    if sender_role == "customer":
        recipient_online = bool(admin and getattr(admin, "is_online", False))
    else:
        recipient_online = bool(peer and getattr(peer, "is_online", False))

    mt = str(message_type or "text").strip().lower()
    try:
        msg_type = MessageType(mt)
    except ValueError:
        msg_type = MessageType.TEXT
    msg = ChatMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_role=sender_role,
        message_type=msg_type,
        content=content,
        media_url=media_url,
        metadata_json=metadata_json,
        is_delivered=recipient_online,
    )
    conv.last_message = (content or message_type)[:500]
    conv.updated_at = utc_now()

    preview = content or ("📷 Photo" if message_type == "image" else "New message")
    if sender_role == "customer":
        conv.unread_admin += 1
        if admin:
            offline_note = "" if recipient_online else " (offline — will see when online)"
            notify(
                session,
                admin.id,
                "chat",
                f"New customer message{offline_note}",
                preview,
                {"conversation_id": conv.id, "offline": not recipient_online},
            )
    elif sender_role in ("admin", "ai", "system"):
        conv.unread_customer += 1
        if peer:
            offline_note = "" if recipient_online else " (you'll see this when back online)"
            notify(
                session,
                peer.id,
                "chat",
                f"SweetCrust replied{offline_note}",
                preview,
                {"conversation_id": conv.id, "offline": not recipient_online},
            )

    session.add(msg)
    session.add(conv)
    session.commit()
    session.refresh(msg)
    emit_chat_message(
        {
            "id": msg.id,
            "content": msg.content,
            "sender_id": sender_id,
            "sender_role": sender_role,
            "message_type": msg_type.value,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        },
        conversation_id=conversation_id,
        peer_user_id=conv.customer_id,
        sender_role=sender_role,
    )
    logger.info("chat message conversation=%s role=%s", conversation_id, sender_role)
    return msg


def list_messages(session: Session, conversation_id: int, user: User) -> list[dict]:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    if conv.customer_id != user.id:
        raise ForbiddenError("Forbidden")

    msgs = list(
        session.exec(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        ).all()
    )
    conv.unread_customer = 0
    for m in msgs:
        if m.sender_role in ("admin", "ai", "system") and not m.is_delivered:
            m.is_delivered = True
            session.add(m)
        if m.sender_role in ("admin", "ai", "system") and not m.is_read:
            m.is_read = True
            session.add(m)
    session.add(conv)
    session.commit()

    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "sender_id": m.sender_id,
            "sender_role": m.sender_role,
            "message_type": m.message_type.value if hasattr(m.message_type, "value") else m.message_type,
            "content": m.content,
            "media_url": m.media_url,
            "metadata_json": m.metadata_json,
            "is_delivered": m.is_delivered,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]
