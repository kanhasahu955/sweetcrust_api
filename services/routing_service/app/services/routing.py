"""Routing domain — stops, ETA, greedy optimize, assign."""
from __future__ import annotations
from sqlmodel import Session
from app.models.enums import OrderStatus
from app.models.ops import DeliveryTracking
from app.repositories import routing as repo
from package.common.errors import NotFoundError
from package.common.utils import haversine_km, utc_now

def bakery_coords(session: Session) -> tuple[float, float]:
    s = repo.bakery_settings(session)
    if s:
        return float(s.latitude), float(s.longitude)
    return 19.1197, 72.8468

def live(session: Session):
    return repo.list_tracking(session)

def _order_coords(session: Session, order) -> tuple[float | None, float | None]:
    track = repo.get_tracking(session, order.id)
    if track and track.customer_lat is not None and track.customer_lng is not None:
        return float(track.customer_lat), float(track.customer_lng)
    snap = order.address_snapshot or {}
    lat = snap.get("latitude") or snap.get("lat")
    lng = snap.get("longitude") or snap.get("lng")
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    return None, None

def open_stops(session: Session) -> list[dict]:
    blat, blng = bakery_coords(session)
    out = []
    for o in repo.open_orders(session):
        lat, lng = _order_coords(session, o)
        dist = round(haversine_km(blat, blng, lat, lng), 2) if lat is not None and lng is not None else None
        out.append({"order_id": o.id, "status": o.status, "lat": lat, "lng": lng,
                    "distance_km": dist, "delivery_person_id": o.delivery_person_id})
    return out

def optimize(session: Session, order_ids: list[int] | None = None) -> dict:
    """Greedy nearest-neighbor from bakery. ponytail: O(n²); upgrade to OR-Tools when routes grow."""
    stops = open_stops(session)
    if order_ids:
        want = set(order_ids)
        stops = [s for s in stops if s["order_id"] in want]
    stops = [s for s in stops if s["lat"] is not None and s["lng"] is not None]
    if not stops:
        return {"route": [], "total_km": 0.0, "stops": 0}
    blat, blng = bakery_coords(session)
    remaining = stops[:]
    route, total = [], 0.0
    cur_lat, cur_lng = blat, blng
    while remaining:
        remaining.sort(key=lambda s: haversine_km(cur_lat, cur_lng, float(s["lat"]), float(s["lng"])))
        nxt = remaining.pop(0)
        d = haversine_km(cur_lat, cur_lng, float(nxt["lat"]), float(nxt["lng"]))
        total += d
        route.append({**nxt, "leg_km": round(d, 2)})
        cur_lat, cur_lng = float(nxt["lat"]), float(nxt["lng"])
    return {"route": route, "total_km": round(total, 2), "stops": len(route)}

def eta(session: Session, order_id: int) -> dict:
    o = repo.get_order(session, order_id)
    if not o:
        raise NotFoundError("Order not found")
    track = repo.get_tracking(session, order_id)
    if track and track.eta_minutes is not None:
        return {"order_id": order_id, "eta_minutes": track.eta_minutes, "source": "tracking"}
    blat, blng = bakery_coords(session)
    lat, lng = _order_coords(session, o)
    if lat is None or lng is None:
        return {"order_id": order_id, "eta_minutes": 45, "source": "default"}
    return {"order_id": order_id, "eta_minutes": max(15, int(haversine_km(blat, blng, lat, lng) * 4)), "source": "distance"}

def assign(session: Session, order_id: int, delivery_person_id: int):
    o = repo.get_order(session, order_id)
    if not o:
        raise NotFoundError("Order not found")
    if not repo.get_rider(session, delivery_person_id):
        raise NotFoundError("Delivery person not found")
    o.delivery_person_id = delivery_person_id
    o.status = OrderStatus.DELIVERY_ASSIGNED
    o.updated_at = utc_now()
    repo.save_order(session, o)
    track = repo.get_tracking(session, order_id)
    if not track:
        track = DeliveryTracking(order_id=order_id, delivery_person_id=delivery_person_id)
    else:
        track.delivery_person_id = delivery_person_id
        track.updated_at = utc_now()
    repo.save_tracking(session, track)
    return o
