"""Picking HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import picking as svc

def status():
    return {"service": "picking", "ready": True}

def queue(session: Session, status: str | None = None):
    return svc.queue(session, status)

def detail(session: Session, order_id: int):
    return svc.detail(session, order_id)

def start(session: Session, order_id: int, actor_id: int):
    return svc.start(session, order_id, actor_id)

def pack(session: Session, order_id: int, actor_id: int):
    return svc.pack(session, order_id, actor_id)

def stats(session: Session):
    return svc.stats(session)
