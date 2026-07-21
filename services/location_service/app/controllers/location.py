"""Location HTTP adapters — addresses + geo."""
from __future__ import annotations
from sqlmodel import Session
from app.services import addresses as address_ops
from app.services import geo as geo_ops

def list_addresses(session: Session, user_id: int):
    return address_ops.list_addresses(session, user_id)

def add_address(session: Session, user, body):
    return address_ops.add_address(session, user, body)

def delete_address(session: Session, user_id: int, address_id: int):
    return address_ops.delete_address(session, user_id, address_id)

def suggest(q: str, limit: int = 6, session_token=None):
    return geo_ops.suggest_addresses(q, limit=limit, session_token=session_token)

def place(place_id: str, session_token=None):
    return geo_ops.place_details(place_id, session_token=session_token)

def reverse(lat: float, lng: float):
    return geo_ops.reverse_geocode(lat, lng)

def pincode(pin: str):
    return geo_ops.lookup_pincode(pin)
