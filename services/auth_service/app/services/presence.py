"""Minimal online/offline presence on User."""
from __future__ import annotations

from sqlmodel import Session

from app.models.user import User
from package.common.utils import utc_now


def set_online(session: Session, user_id: int) -> User | None:
    user = session.get(User, user_id)
    if not user:
        return None
    user.is_online = True
    user.last_seen_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def set_offline(session: Session, user_id: int) -> User | None:
    user = session.get(User, user_id)
    if not user:
        return None
    user.is_online = False
    user.last_seen_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
