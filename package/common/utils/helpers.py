import math
import re
import secrets
import string
from typing import Optional

from package.common.utils.datetime import utc_now


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-")[:200]


def generate_order_number() -> str:
    stamp = utc_now().strftime("%y%m%d")
    suffix = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"SC{stamp}{suffix}"


def generate_invoice_number(prefix: str = "INV") -> str:
    stamp = utc_now().strftime("%Y%m")
    suffix = "".join(secrets.choice(string.digits) for _ in range(5))
    tag = (prefix or "INV").strip().upper()[:8] or "INV"
    return f"{tag}-{stamp}-{suffix}"


def generate_txn_id(prefix: str = "TXN") -> str:
    return f"{prefix}{secrets.token_hex(8).upper()}"


def calc_discount(original: Optional[float], selling: float) -> float:
    if not original or original <= selling:
        return 0.0
    return round(((original - selling) / original) * 100, 1)


def calc_gst(amount: float, rate: float = 5.0) -> float:
    return round(amount * rate / (100 + rate), 2)


def stock_status_for(qty: int, threshold: int = 5) -> str:
    if qty <= 0:
        return "out_of_stock"
    if qty <= threshold:
        return "low_stock"
    return "in_stock"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)
