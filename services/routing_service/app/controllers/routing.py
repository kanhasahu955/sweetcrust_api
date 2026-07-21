"""Routing HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import routing as svc

def status():
    return {"service": "routing", "ready": True}

def live(session: Session):
    return svc.live(session)

def stops(session: Session):
    return svc.open_stops(session)

def optimize(session: Session, order_ids=None):
    return svc.optimize(session, order_ids)

def eta(session: Session, order_id: int):
    return svc.eta(session, order_id)

def assign(session: Session, order_id: int, delivery_person_id: int):
    return svc.assign(session, order_id, delivery_person_id)
