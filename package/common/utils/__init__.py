"""Shared helpers — datetime, slugify, passwords, etc."""

from package.common.utils.datetime import day_bounds, days_ago, utc_now, utc_now_aware, utc_today
from package.common.utils.helpers import (
    calc_discount,
    calc_gst,
    generate_invoice_number,
    generate_order_number,
    generate_txn_id,
    haversine_km,
    slugify,
    stock_status_for,
)
from package.common.utils.security import hash_password, verify_password

__all__ = [
    "utc_now",
    "utc_now_aware",
    "utc_today",
    "day_bounds",
    "days_ago",
    "slugify",
    "generate_order_number",
    "generate_invoice_number",
    "generate_txn_id",
    "calc_discount",
    "calc_gst",
    "stock_status_for",
    "haversine_km",
    "hash_password",
    "verify_password",
]
