"""Notification HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services.notifications import list_notifications, mark_read

def list_all(session: Session, user_id: int, unread_only: bool = False):
    return list_notifications(session, user_id, unread_only)

def mark(session: Session, user_id: int, notification_id: int | None = None):
    return mark_read(session, user_id, notification_id)
