"""Address suggest / details via Google Places + Geocoding.

Degrades cleanly when GOOGLE_MAPS_API_KEY is missing (empty / None results).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from package.logger import get_logger

logger = get_logger(__name__)

_AUTOCOMPLETE = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
_GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"


def _key() -> str | None:
    key = (get_settings().google_maps_api_key or "").strip()
    return key or None


def _pick(*vals: Any) -> str | None:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _component_map(components: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in components or []:
        long_name = c.get("long_name") or ""
        for t in c.get("types") or []:
            out[t] = long_name
    return out


def _strip_country(formatted: str | None) -> str | None:
    if not formatted:
        return None
    s = formatted.strip()
    for suffix in (", India", ", Bharat"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s or None


def _from_google_result(result: dict, *, label: str | None = None) -> dict:
    comps = _component_map(result.get("address_components") or [])
    name = _pick(result.get("name"))
    street = _pick(
        " ".join(x for x in [comps.get("street_number"), comps.get("route")] if x).strip() or None,
        comps.get("route"),
    )
    area = _pick(
        comps.get("sublocality_level_1"),
        comps.get("sublocality"),
        comps.get("neighborhood"),
    )
    locality = _pick(comps.get("locality"), comps.get("postal_town"))
    district = _pick(comps.get("administrative_area_level_2"))
    state = _pick(comps.get("administrative_area_level_1"))
    pincode = _pick(comps.get("postal_code"))
    city = locality or district
    village = _pick(comps.get("sublocality_level_2"), area, locality)
    if village and city and village == city and area and area != city:
        village = area

    formatted = _pick(result.get("formatted_address"), label)
    short_fmt = _strip_country(formatted)
    if name and street and name.lower() not in street.lower():
        address_line = f"{name}, {street}"
    else:
        address_line = _pick(name, street, short_fmt, locality, area) or ""

    loc = (result.get("geometry") or {}).get("location") or {}
    try:
        lat = float(loc["lat"])
        lng = float(loc["lng"])
    except (KeyError, TypeError, ValueError):
        lat = lng = None
    return {
        "label": formatted or address_line,
        "address_line": address_line,
        "village": village,
        "area": area,
        "city": city,
        "state": state,
        "pincode": pincode,
        "zone": None,
        "latitude": lat,
        "longitude": lng,
        "place_id": result.get("place_id"),
    }


def suggest_addresses(q: str, *, limit: int = 6, session_token: str | None = None) -> list[dict]:
    query = (q or "").strip()
    if len(query) < 2:
        return []
    key = _key()
    if not key:
        logger.info("geo suggest degraded: GOOGLE_MAPS_API_KEY missing")
        return []
    params: dict[str, Any] = {
        "input": query,
        "key": key,
        "components": "country:in",
        "language": "en",
    }
    if session_token:
        params["sessiontoken"] = session_token
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(_AUTOCOMPLETE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("google places autocomplete failed")
        return []
    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        logger.warning("google autocomplete status=%s error=%s", status, data.get("error_message"))
        return []
    out: list[dict] = []
    for pred in (data.get("predictions") or [])[:limit]:
        place_id = pred.get("place_id")
        label = pred.get("description") or ""
        if not place_id or not label:
            continue
        structured = pred.get("structured_formatting") or {}
        parts = [p.strip() for p in label.split(",") if p.strip()]
        city = parts[-3] if len(parts) >= 3 else None
        state = parts[-2] if len(parts) >= 2 else None
        if state and state.lower() in ("india", "bharat"):
            state = parts[-3] if len(parts) >= 3 else None
            city = parts[-4] if len(parts) >= 4 else parts[0] if parts else None
        out.append(
            {
                "place_id": place_id,
                "label": label,
                "address_line": structured.get("main_text") or label,
                "village": None,
                "area": None,
                "city": city,
                "state": state,
                "pincode": None,
                "zone": None,
                "latitude": None,
                "longitude": None,
            }
        )
    return out


def place_details(place_id: str, *, session_token: str | None = None) -> dict | None:
    if not (place_id or "").strip():
        return None
    key = _key()
    if not key:
        logger.info("geo place_details degraded: GOOGLE_MAPS_API_KEY missing")
        return None
    params: dict[str, Any] = {
        "place_id": place_id.strip(),
        "key": key,
        "fields": "place_id,name,formatted_address,address_components,geometry",
        "language": "en",
    }
    if session_token:
        params["sessiontoken"] = session_token
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(_DETAILS, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("google place details failed")
        return None
    if data.get("status") != "OK":
        logger.warning("google details status=%s", data.get("status"))
        return None
    return _from_google_result(data.get("result") or {})


def geocode_query(q: str) -> dict | None:
    query = (q or "").strip()
    if not query:
        return None
    key = _key()
    if not key:
        return None
    params = {"address": query, "key": key, "region": "in", "language": "en"}
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(_GEOCODE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("google geocode failed")
        return None
    if data.get("status") != "OK":
        return None
    results = data.get("results") or []
    if not results:
        return None
    return _from_google_result(results[0])


def reverse_geocode(lat: float, lng: float) -> dict | None:
    key = _key()
    if not key:
        logger.info("geo reverse degraded: GOOGLE_MAPS_API_KEY missing")
        return None
    params = {
        "latlng": f"{lat},{lng}",
        "key": key,
        "language": "en",
        "result_type": "street_address|premise|sublocality|locality",
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(_GEOCODE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("google reverse geocode failed")
        return None
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        logger.warning("google reverse status=%s", data.get("status"))
        return None
    results = data.get("results") or []
    if not results:
        params.pop("result_type", None)
        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.get(_GEOCODE, params=params)
                data = resp.json()
            results = data.get("results") or []
        except Exception:
            return None
    if not results:
        return None
    row = _from_google_result(results[0])
    row["latitude"] = float(lat)
    row["longitude"] = float(lng)
    return row


def lookup_pincode(pin: str) -> dict | None:
    digits = "".join(c for c in (pin or "") if c.isdigit())
    if len(digits) != 6:
        return None
    return geocode_query(f"{digits}, India")


def geocode_fill(parts: dict) -> dict:
    if parts.get("latitude") is not None and parts.get("longitude") is not None:
        return parts
    bits = [
        parts.get("address_line"),
        parts.get("village"),
        parts.get("city"),
        parts.get("state"),
        parts.get("pincode"),
        "India",
    ]
    hit = geocode_query(", ".join(b for b in bits if b))
    if not hit:
        return parts
    return {
        **parts,
        "latitude": hit.get("latitude"),
        "longitude": hit.get("longitude"),
        "city": parts.get("city") or hit.get("city"),
        "state": parts.get("state") or hit.get("state"),
        "pincode": parts.get("pincode") or hit.get("pincode"),
        "area": parts.get("area") or hit.get("area"),
        "village": parts.get("village") or hit.get("village"),
        "address_line": parts.get("address_line") or hit.get("address_line"),
        "zone": parts.get("zone") or hit.get("zone"),
        "place_id": hit.get("place_id"),
    }
