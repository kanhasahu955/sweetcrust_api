"""Pricing HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import pricing as svc

def status():
    return {"service": "pricing", "ready": True}

def quote(session: Session, product_id: int, channel: str = "customer"):
    return svc.quote(session, product_id, channel)

def quote_bulk(session: Session, product_ids: list[int], channel: str = "customer"):
    return svc.quote_bulk(session, product_ids, channel)

def estimate_cake(weight: str, budget_max: float | None = None):
    return svc.estimate_custom_cake(weight, budget_max)

def list_products(session: Session, page: int = 1, page_size: int = 50):
    return svc.list_priced(session, page, page_size)

def get_product(session: Session, product_id: int):
    return svc.quote(session, product_id, "customer")

def patch_product(session: Session, product_id: int, data: dict):
    return svc.update_prices(session, product_id, data)
