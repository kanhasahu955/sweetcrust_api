"""Chat / conversation persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import ChatMessage, Conversation

def get_conversation(session: Session, conversation_id: int) -> Conversation | None:
    return session.get(Conversation, conversation_id)

def list_for_customer(session: Session, customer_id: int) -> list[Conversation]:
    return list(session.exec(select(Conversation).where(Conversation.customer_id == customer_id).order_by(Conversation.updated_at.desc())).all())

def messages(session: Session, conversation_id: int) -> list[ChatMessage]:
    return list(session.exec(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at)).all())

def save(session: Session, obj):
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
