"""Support chat HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import chats as chat_ops

def create_chat(session: Session, user_id: int, body):
    return chat_ops.create_conversation(session, user_id, body)

def list_chats(session: Session, user):
    return chat_ops.list_conversations(session, user)

def list_messages(session: Session, conversation_id: int, user):
    return chat_ops.list_messages(session, conversation_id, user)

def send(session: Session, conversation_id: int, user_id: int, body):
    return chat_ops.send_message(
        session, conversation_id, user_id, "customer",
        body.content, body.message_type, body.media_url, body.metadata_json,
    )
