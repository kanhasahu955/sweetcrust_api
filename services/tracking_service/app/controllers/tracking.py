"""Tracking HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import engagement as engage_ops
from app.services import orders as order_ops

def track(session: Session, order_id: int, user_id: int):
    return order_ops.track_order(session, order_id, user_id)

def share(session: Session, user, order_id: int):
    return engage_ops.create_share_link(session, user, order_id)

def public_track(session: Session, token: str):
    return engage_ops.public_track(session, token)
