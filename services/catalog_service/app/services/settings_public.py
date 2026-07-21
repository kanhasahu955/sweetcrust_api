"""Public bakery settings for the customer app (slots, phone, hours)."""
from __future__ import annotations

from datetime import time

from sqlmodel import Session, select

from app.models.ops import BakerySettings


def _slots_from_hours(open_t: time | None, close_t: time | None) -> list[str]:
    if not open_t or not close_t:
        return []
    start = open_t.hour * 60 + open_t.minute
    end = close_t.hour * 60 + close_t.minute
    if end <= start:
        return []
    slots: list[str] = []
    t = start
    while t + 120 <= end:
        a, b = t, t + 120
        slots.append(f"{a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d}")
        t += 120
    return slots


def public_settings(session: Session) -> dict:
    row = session.exec(select(BakerySettings)).first()
    slots: list[str] = []
    hours = row.working_hours if row else None
    if isinstance(hours, dict):
        raw = hours.get("delivery_slots") or hours.get("slots") or []
        if isinstance(raw, list):
            slots = [str(x) for x in raw if x]
    if not slots and row:
        slots = _slots_from_hours(row.open_time, row.close_time)
    return {
        "bakery_name": row.bakery_name if row else None,
        "phone": row.phone if row else None,
        "email": row.email if row else None,
        "address": row.address if row else None,
        "latitude": float(row.latitude) if row else None,
        "longitude": float(row.longitude) if row else None,
        "upi_id": row.upi_id if row else None,
        "delivery_slots": slots,
        "delivery_charge": float(row.delivery_charge) if row else None,
        "free_delivery_min": float(row.free_delivery_min) if row else None,
        "min_order_value": float(row.min_order_value) if row else None,
        "cod_enabled": bool(row.cod_enabled) if row else True,
        "open_time": row.open_time.isoformat() if row and row.open_time else None,
        "close_time": row.close_time.isoformat() if row and row.close_time else None,
    }
