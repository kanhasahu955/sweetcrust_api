"""Forecast HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import forecast as svc

def status():
    return {"service": "forecast", "ready": True}

def demand(session: Session, period: str = "weekly"):
    return svc.demand(session, period)

def stockout(session: Session, period: str = "weekly"):
    return svc.stockout(session, period)

def revenue(session: Session, period: str = "weekly"):
    return svc.revenue(session, period)

def sku(session: Session, product_id: int, period: str = "weekly"):
    return svc.sku(session, product_id, period)
