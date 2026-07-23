"""Canonical sell / catalog unit labels for shop + admin UIs."""

from __future__ import annotations

DEFAULT_UNIT = "pcs"

# ponytail: static catalog (no DB). Upgrade: Unit table + admin CRUD if shops need custom units.
UNITS: list[dict[str, str]] = [
    {"code": "pcs", "label": "Piece (pcs)"},
    {"code": "pkt", "label": "Packet (pkt)"},
    {"code": "pack", "label": "Pack"},
    {"code": "box", "label": "Box"},
    {"code": "jar", "label": "Jar"},
    {"code": "tin", "label": "Tin"},
    {"code": "bottle", "label": "Bottle"},
    {"code": "tray", "label": "Tray"},
    {"code": "dozen", "label": "Dozen"},
    {"code": "kg", "label": "Kilogram (kg)"},
    {"code": "g", "label": "Gram (g)"},
    {"code": "L", "label": "Litre (L)"},
    {"code": "ml", "label": "Millilitre (ml)"},
    {"code": "bunch", "label": "Bunch"},
]

_ALIASES = {
    "pc": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
    "packet": "pkt",
    "packets": "pkt",
    "packs": "pack",
    "kilogram": "kg",
    "kilograms": "kg",
    "gram": "g",
    "grams": "g",
    "liter": "L",
    "litre": "L",
    "liters": "L",
    "litres": "L",
    "milliliter": "ml",
    "millilitre": "ml",
}


def list_units() -> list[dict[str, str]]:
    return [dict(u) for u in UNITS]


def unit_codes() -> set[str]:
    return {u["code"] for u in UNITS}


def normalize_unit(raw: str | None) -> str:
    code = str(raw or DEFAULT_UNIT).strip()
    if not code:
        return DEFAULT_UNIT
    key = code.lower()
    mapped = _ALIASES.get(key, code if code in unit_codes() else key)
    # preserve canonical casing for L
    for u in UNITS:
        if u["code"].lower() == mapped.lower():
            return u["code"]
    return DEFAULT_UNIT


def _self_check() -> None:
    codes = unit_codes()
    assert DEFAULT_UNIT in codes
    assert normalize_unit("packet") == "pkt"
    assert normalize_unit("PC") == "pcs"
    assert normalize_unit("nope") == DEFAULT_UNIT


_self_check()
