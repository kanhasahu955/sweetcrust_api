"""Catalog controllers — HTTP adapters → domain services."""
from __future__ import annotations

from sqlmodel import Session

from app.services import geo as geo_svc
from app.services import products as product_svc


def home(session: Session, user_id: int | None = None):
    return product_svc.home_feed(session, user_id=user_id)


def categories(session: Session, active_only: bool = True):
    return product_svc.list_categories(session, active_only=active_only)


def products(session: Session, query):
    return product_svc.list_products(session, query)


def product_detail(session: Session, product_id: int, user_id: int | None = None):
    return product_svc.product_detail(session, product_id, user_id=user_id)


def toggle_favorite(session: Session, user_id: int, product_id: int):
    return product_svc.toggle_favorite(session, user_id, product_id)


def add_review(session: Session, user_id: int, product_id: int, **kwargs):
    return product_svc.add_review(session, user_id, product_id, **kwargs)


def geo_suggest(q: str, **kwargs):
    return geo_svc.suggest_addresses(q, **kwargs)


def geo_place(place_id: str, **kwargs):
    return geo_svc.place_details(place_id, **kwargs)


def geo_reverse(lat: float, lng: float):
    return geo_svc.reverse_geocode(lat, lng)


def geo_pincode(pin: str):
    return geo_svc.lookup_pincode(pin)
