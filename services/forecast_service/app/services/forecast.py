"""Forecast domain — demand, stockout risk, revenue, SKU velocity."""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from sqlmodel import Session
from app.models.enums import OrderStatus, PaymentStatus, StockStatus
from app.repositories import sales as sales_repo
from package.common.utils import utc_now

def _paid(orders) -> list:
    return [
        o for o in orders
        if o.payment_status == PaymentStatus.PAID
        or (str(o.order_type or "").startswith("b2b") and o.status == OrderStatus.DELIVERED)
    ]

def demand(session: Session, period: str = "weekly") -> dict:
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    since = utc_now() - timedelta(days=days)
    paid = _paid(sales_repo.orders_since(session, since))
    by_day: dict[str, float] = defaultdict(float)
    by_sku: dict[str, int] = defaultdict(int)
    order_ids = [o.id for o in paid if o.id]
    for o in paid:
        key = o.created_at.date().isoformat() if o.created_at else "unknown"
        by_day[key] += float(o.final_amount or 0)
    for it in sales_repo.items_for_orders(session, order_ids):
        by_sku[it.product_name] += int(it.quantity or 0)
    daily_avg = (sum(by_day.values()) / max(len(by_day), 1)) if by_day else 0.0
    return {
        "period": period, "days": days,
        "series": [{"date": k, "revenue": round(v, 2)} for k, v in sorted(by_day.items())],
        "top_skus": sorted(({"name": k, "qty": v} for k, v in by_sku.items()), key=lambda x: -x["qty"])[:20],
        "projected_revenue": round(daily_avg * days, 2),
        "note": "ponytail: naive avg projection; upgrade to seasonal model when history grows",
    }

def stockout(session: Session, period: str = "weekly") -> dict:
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    since = utc_now() - timedelta(days=days)
    paid = _paid(sales_repo.orders_since(session, since))
    order_ids = [o.id for o in paid if o.id]
    sold: dict[int, int] = defaultdict(int)
    for it in sales_repo.items_for_orders(session, order_ids):
        sold[it.product_id] += int(it.quantity or 0)
    risk = []
    for p in sales_repo.active_products(session):
        velocity = sold.get(p.id or 0, 0) / max(days, 1)
        days_left = round((p.stock_qty or 0) / velocity, 1) if velocity > 0 else None
        if (p.stock_status == StockStatus.OUT_OF_STOCK) or (days_left is not None and days_left < 3) or (p.stock_qty or 0) <= (p.low_stock_threshold or 5):
            risk.append({
                "product_id": p.id, "name": p.name, "stock_qty": p.stock_qty,
                "velocity_per_day": round(velocity, 2), "days_of_cover": days_left,
                "stock_status": p.stock_status,
            })
    risk.sort(key=lambda r: (r["days_of_cover"] is None, r["days_of_cover"] or 0))
    return {"period": period, "at_risk": risk[:50], "count": len(risk)}

def revenue(session: Session, period: str = "weekly") -> dict:
    d = demand(session, period)
    return {"period": period, "projected_revenue": d["projected_revenue"], "series": d["series"]}

def sku(session: Session, product_id: int, period: str = "weekly") -> dict:
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    since = utc_now() - timedelta(days=days)
    p = sales_repo.get_product(session, product_id)
    paid = _paid(sales_repo.orders_since(session, since))
    order_ids = [o.id for o in paid if o.id]
    qty = sum(int(it.quantity or 0) for it in sales_repo.items_for_product(session, order_ids, product_id))
    return {
        "product_id": product_id, "name": p.name if p else None, "period": period,
        "units_sold": qty, "avg_per_day": round(qty / max(days, 1), 2), "projected_units": qty,
    }
