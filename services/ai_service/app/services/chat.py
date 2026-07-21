from datetime import datetime

from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from sqlmodel import Session, select

from app.models.enums import ChatCategory, MessageType, UserRole
from app.models.ops import ChatMessage, Conversation
from app.models.user import User
from app.services.notify import notify


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
        role = "retailer" if str(cat).startswith("retailer") else "customer"
        send_message(session, conv.id, customer_id, role, data.initial_message)
    return conv


def get_or_create_retailer_support(session: Session, retailer_id: int, *, ai: bool = False) -> Conversation:
    cat = ChatCategory.RETAILER_AI if ai else ChatCategory.RETAILER
    existing = session.exec(
        select(Conversation)
        .where(
            Conversation.customer_id == retailer_id,
            Conversation.category == cat,
        )
        .order_by(Conversation.updated_at.desc())
    ).first()
    if existing and (not ai or existing.is_ai or not existing.ai_handed_over):
        return existing
    from types import SimpleNamespace

    return create_conversation(
        session,
        retailer_id,
        SimpleNamespace(
            category=cat.value,
            order_id=None,
            return_id=None,
            custom_cake_id=None,
            is_ai=ai,
            initial_message=None,
        ),
    )


def list_conversations(session: Session, user: User) -> list[dict]:
    if user.role == UserRole.ADMIN:
        rows = list(session.exec(select(Conversation).order_by(Conversation.updated_at.desc())).all())
    elif user.role == UserRole.RETAILER:
        rows = list(
            session.exec(
                select(Conversation)
                .where(Conversation.customer_id == user.id)
                .order_by(Conversation.updated_at.desc())
            ).all()
        )
    else:
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
    is_retailer = cat.startswith("retailer")
    return {
        "id": conv.id,
        "category": cat,
        "customer_id": conv.customer_id,
        "participant_id": conv.customer_id,
        "participant_role": "retailer" if is_retailer else "customer",
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
    *,
    skip_guardrails: bool = False,
) -> ChatMessage:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    if (
        not skip_guardrails
        and sender_role in ("customer", "retailer")
        and content
        and message_type == "text"
    ):
        from app.brain.guardrails import filter_user_message

        # Peer human chat: only hard-block NSFW; AI chats keep topic gate
        cat = conv.category.value if hasattr(conv.category, "value") else str(conv.category)
        mode = "ai" if conv.is_ai or str(cat).endswith("_ai") or str(cat) == "ai" else "peer"
        gate = filter_user_message(content, mode=mode)
        if not gate.get("allowed"):
            raise BadRequestError(gate.get("reply") or "Message blocked by app rules")
        content = gate.get("text") or content
    if sender_role == "ai" and content:
        from app.brain.guardrails import filter_ai_reply

        content = filter_ai_reply(content)

    peer = session.get(User, conv.customer_id)
    admin = _first_admin(session)
    # Delivered immediately if recipient is online; else queued via unread + notification
    if sender_role in ("customer", "retailer"):
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
    conv.updated_at = datetime.utcnow()

    preview = content or ("📷 Photo" if message_type == "image" else "New message")
    if sender_role in ("customer", "retailer"):
        conv.unread_admin += 1
        if admin:
            offline_note = "" if recipient_online else " (offline — will see when online)"
            notify(
                session,
                admin.id,
                "chat",
                f"New {'shop' if sender_role == 'retailer' else 'customer'} message{offline_note}",
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
    try:
        from app.producers.events import message_payload, schedule_chat_broadcast

        schedule_chat_broadcast(
            message_payload(msg),
            conversation_id=conversation_id,
            peer_user_id=conv.customer_id,
            sender_role=sender_role,
        )
    except Exception:
        pass
    return msg


def require_conversation(session: Session, conversation_id: int, user: User) -> Conversation:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    if user.role != UserRole.ADMIN and conv.customer_id != user.id:
        raise ForbiddenError("Forbidden")
    return conv


def llm_history(session: Session, conversation_id: int, *, limit: int = 12) -> list[dict[str, str]]:
    """Last N turns as OpenAI-style role/content for the chatbot graph."""
    rows = list(
        session.exec(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()
    )
    rows.reverse()
    out: list[dict[str, str]] = []
    for m in rows:
        text = (m.content or "").strip()
        if not text:
            continue
        if m.sender_role in ("customer", "retailer", "user"):
            role = "user"
        elif m.sender_role in ("ai", "assistant"):
            role = "assistant"
        else:
            continue
        out.append({"role": role, "content": text})
    return out


def list_messages(session: Session, conversation_id: int, user: User) -> list[dict]:
    conv = require_conversation(session, conversation_id, user)

    # Mark delivered + read for the viewer (offline messages catch up here)
    msgs = list(
        session.exec(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        ).all()
    )
    if user.role == UserRole.ADMIN:
        conv.unread_admin = 0
        for m in msgs:
            if m.sender_role in ("customer", "retailer") and not m.is_delivered:
                m.is_delivered = True
                session.add(m)
            if m.sender_role in ("customer", "retailer") and not m.is_read:
                m.is_read = True
                session.add(m)
    else:
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


def handover_to_admin(session: Session, conversation_id: int) -> Conversation:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    conv.is_ai = False
    conv.ai_handed_over = True
    admin = _first_admin(session)
    if admin:
        conv.admin_id = admin.id
        notify(
            session,
            admin.id,
            "ai",
            "AI chat escalated",
            "A shop/customer needs human support",
            {"conversation_id": conv.id},
        )
    session.add(conv)
    send_message(
        session,
        conversation_id,
        None,
        "system",
        "Connecting you to SweetCrust bakery owner. Please wait…",
        message_type="system",
        skip_guardrails=True,
    )
    session.refresh(conv)
    return conv


def request_admin_callback(session: Session, user: User, note: str | None = None) -> dict:
    """Retailer/customer requests a phone callback — creates call record + notifies admin."""
    from app.models.enums import CallStatus, CallType
    from app.models.ops import BakerySettings, CallRecord

    admin = _first_admin(session)
    settings = session.exec(select(BakerySettings)).first()
    bakery_phone = (settings.phone if settings else None) or (admin.phone if admin else None)
    rec = CallRecord(
        caller_id=user.id,
        callee_id=admin.id if admin else None,
        call_type=CallType.PHONE,
        status=CallStatus.RINGING,
        direction="inbound",
        provider="phone",
        to_phone=bakery_phone,
        purpose=note or "Callback request from app",
        notes=f"{user.role.value if hasattr(user.role, 'value') else user.role}: {user.name or user.phone}",
        started_at=datetime.utcnow(),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    if admin:
        notify(
            session,
            admin.id,
            "call",
            "Callback requested",
            f"{user.name or user.phone} wants a call" + (f" — {note}" if note else ""),
            {"call_id": rec.id, "from_user_id": user.id},
        )
    # Also drop a system line in support chat for retailers
    if user.role == UserRole.RETAILER:
        conv = get_or_create_retailer_support(session, user.id, ai=False)
        send_message(
            session,
            conv.id,
            user.id,
            "retailer",
            f"📞 Callback requested{': ' + note if note else ''}. Bakery phone: {bakery_phone or '—'}",
            skip_guardrails=True,
        )
    return {
        "call_id": rec.id,
        "status": "requested",
        "bakery_phone": bakery_phone,
        "message": "Owner notified. You can also dial the bakery number shown.",
    }
