"""Retailer shop analytics — daily / weekly / monthly sales views."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, time
from typing import Any

from sqlmodel import Session, col, select

from app.models.catalog import Category, Product
from app.models.commerce import Order, OrderItem
from app.models.enums import OrderStatus
from app.models.user import RetailerProfile, User
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)

_CANCELLED = {OrderStatus.CANCELLED, OrderStatus.REJECTED}
_PERIODS = frozenset({"daily", "weekly", "monthly"})


def _shop(session: Session, user: User) -> RetailerProfile:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    return profile


def _parse_anchor(raw: str | None) -> date:
    if not raw:
        return utc_now().date()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise BadRequestError("anchor must be YYYY-MM-DD") from exc


def _period_bounds(period: str, anchor: date) -> tuple[datetime, datetime, datetime, datetime, str]:
    """Return (start, end_exclusive, prev_start, prev_end_exclusive, label)."""
    if period == "daily":
        start = datetime.combine(anchor, time.min)
        end = start + timedelta(days=1)
        prev_start = start - timedelta(days=1)
        prev_end = start
        label = anchor.strftime("%d %b %Y, %a")
    elif period == "weekly":
        # Week starting Monday
        start_d = anchor - timedelta(days=anchor.weekday())
        start = datetime.combine(start_d, time.min)
        end = start + timedelta(days=7)
        prev_start = start - timedelta(days=7)
        prev_end = start
        end_d = (end - timedelta(seconds=1)).date()
        label = f"{start_d.strftime('%d %b')} – {end_d.strftime('%d %b %Y')}"
    else:  # monthly
        start = datetime.combine(anchor.replace(day=1), time.min)
        if anchor.month == 12:
            end = datetime.combine(date(anchor.year + 1, 1, 1), time.min)
        else:
            end = datetime.combine(date(anchor.year, anchor.month + 1, 1), time.min)
        prev_end = start
        if start.month == 1:
            prev_start = datetime.combine(date(start.year - 1, 12, 1), time.min)
        else:
            prev_start = datetime.combine(date(start.year, start.month - 1, 1), time.min)
        label = anchor.strftime("%B %Y")
    return start, end, prev_start, prev_end, label


def _orders_between(session: Session, shop_user_id: int, start: datetime, end: datetime) -> list[Order]:
    return list(
        session.exec(
            select(Order)
            .where(
                Order.shop_user_id == shop_user_id,
                col(Order.created_at) >= start,
                col(Order.created_at) < end,
            )
            .order_by(Order.created_at.asc())
        ).all()
    )


def _is_sale(order: Order) -> bool:
    st = order.status
    if st in _CANCELLED:
        return False
    # count all non-cancelled shop orders as sales volume
    return True


def _bucket_series(period: str, start: datetime, end: datetime, orders: list[Order]) -> list[dict]:
    sales = [o for o in orders if _is_sale(o)]
    if period == "daily":
        # 4-hour buckets
        buckets: list[dict] = []
        for h in range(0, 24, 4):
            b0 = start + timedelta(hours=h)
            b1 = b0 + timedelta(hours=4)
            amt = sum(float(o.final_amount or 0) for o in sales if b0 <= (o.created_at or start) < b1)
            hr = b0.hour
            ampm = "AM" if hr < 12 else "PM"
            hr12 = hr % 12 or 12
            buckets.append({"label": f"{hr12} {ampm}", "amount": round(amt, 2), "hour": hr})
        return buckets
    if period == "weekly":
        buckets = []
        for i in range(7):
            d0 = start + timedelta(days=i)
            d1 = d0 + timedelta(days=1)
            amt = sum(float(o.final_amount or 0) for o in sales if d0 <= (o.created_at or start) < d1)
            buckets.append({"label": d0.strftime("%a"), "amount": round(amt, 2), "day": d0.date().isoformat()})
        return buckets
    # monthly — by day of month
    buckets = []
    cur = start
    while cur < end:
        nxt = cur + timedelta(days=1)
        amt = sum(float(o.final_amount or 0) for o in sales if cur <= (o.created_at or start) < nxt)
        buckets.append({"label": str(cur.day), "amount": round(amt, 2), "day": cur.date().isoformat()})
        cur = nxt
    return buckets


def _peak_window(series: list[dict], period: str) -> dict | None:
    if not series:
        return None
    best_i = max(range(len(series)), key=lambda i: float(series[i].get("amount") or 0))
    if float(series[best_i].get("amount") or 0) <= 0:
        return None
    if period == "daily":
        h = int(series[best_i].get("hour") or 0)
        end_h = h + 4
        def fmt(x: int) -> str:
            ampm = "AM" if x % 24 < 12 else "PM"
            hr12 = (x % 24) % 12 or 12
            return f"{hr12} {ampm}"
        return {
            "label": f"{fmt(h)} – {fmt(end_h)}",
            "amount": series[best_i]["amount"],
            "index": best_i,
        }
    return {
        "label": str(series[best_i].get("label") or ""),
        "amount": series[best_i]["amount"],
        "index": best_i,
    }


def _line_totals(session: Session, order_ids: list[int]) -> tuple[list[dict], list[dict], float]:
    if not order_ids:
        return [], [], 0.0
    items = list(session.exec(select(OrderItem).where(col(OrderItem.order_id).in_(order_ids))).all())
    by_product: dict[int, dict[str, Any]] = {}
    by_cat: dict[str, float] = defaultdict(float)
    gst_total = 0.0
    # gst is on order — caller passes separately; here product/category only
    product_ids = {i.product_id for i in items if i.product_id}
    products = {
        p.id: p
        for p in session.exec(select(Product).where(col(Product.id).in_(list(product_ids)))).all()
    } if product_ids else {}
    cat_ids = {p.category_id for p in products.values()}
    cats = {
        c.id: c.name
        for c in session.exec(select(Category).where(col(Category.id).in_(list(cat_ids)))).all()
    } if cat_ids else {}

    for i in items:
        pid = int(i.product_id or 0)
        row = by_product.get(pid) or {
            "product_id": pid,
            "product_name": i.product_name,
            "qty": 0,
            "amount": 0.0,
        }
        row["qty"] = int(row["qty"]) + int(i.quantity or 0)
        row["amount"] = round(float(row["amount"]) + float(i.total_price or 0), 2)
        by_product[pid] = row
        p = products.get(pid)
        cat_name = cats.get(p.category_id) if p else "Other"
        by_cat[cat_name or "Other"] += float(i.total_price or 0)

    top_products = sorted(by_product.values(), key=lambda r: r["amount"], reverse=True)[:8]
    categories = [
        {"name": name, "amount": round(amt, 2)}
        for name, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    ]
    return top_products, categories, gst_total


def _insights(
    *,
    total: float,
    prev_total: float,
    change_pct: float | None,
    peak: dict | None,
    top_products: list[dict],
    low_stock: list[dict],
) -> list[dict]:
    out: list[dict] = []
    # Forecast: simple +change or +8%
    if total > 0:
        mult = 1.08 if (change_pct is None or change_pct >= 0) else 0.95
        lo = round(total * mult * 0.95, 0)
        hi = round(total * mult * 1.08, 0)
        badge = "High Growth" if (change_pct or 0) >= 10 else "Steady"
        out.append(
            {
                "id": "forecast",
                "title": "Sales Forecast",
                "body": f"Next period outlook ₹{lo:,.0f} – ₹{hi:,.0f} based on current pace.",
                "badge": badge,
                "tone": "success" if badge == "High Growth" else "neutral",
            }
        )
    if peak and peak.get("label"):
        out.append(
            {
                "id": "peak",
                "title": "Best-selling Time",
                "body": f"Peak window {peak['label']} · {_inr(peak.get('amount'))} in that slot.",
                "badge": "Peak",
                "tone": "ember",
            }
        )
    if top_products:
        names = ", ".join(p["product_name"] for p in top_products[:3])
        out.append(
            {
                "id": "top",
                "title": "Top performers",
                "body": f"Leaders this period: {names}. Keep these stocked.",
                "badge": "Demand",
                "tone": "ember",
            }
        )
    if low_stock:
        out.append(
            {
                "id": "stock",
                "title": "Stock Recommendations",
                "body": f"Restock {len(low_stock)} product{'s' if len(low_stock) != 1 else ''} running low.",
                "badge": "Action Suggested",
                "tone": "info",
            }
        )
    if not out:
        out.append(
            {
                "id": "empty",
                "title": "Getting started",
                "body": "Sales insights appear after your shop records customer orders.",
                "badge": "Tip",
                "tone": "neutral",
            }
        )
    return out[:4]


def _inr(v: Any) -> str:
    try:
        return f"₹{float(v or 0):,.0f}"
    except (TypeError, ValueError):
        return "₹0"


def shop_analytics(
    session: Session,
    user: User,
    *,
    period: str = "daily",
    anchor: str | None = None,
) -> dict:
    period = (period or "daily").strip().lower()
    if period not in _PERIODS:
        raise BadRequestError("period must be daily, weekly, or monthly")
    _shop(session, user)
    day = _parse_anchor(anchor)
    start, end, prev_start, prev_end, label = _period_bounds(period, day)

    cur_orders = _orders_between(session, user.id, start, end)
    prev_orders = _orders_between(session, user.id, prev_start, prev_end)
    cur_sales = [o for o in cur_orders if _is_sale(o)]
    prev_sales = [o for o in prev_orders if _is_sale(o)]

    total = round(sum(float(o.final_amount or 0) for o in cur_sales), 2)
    prev_total = round(sum(float(o.final_amount or 0) for o in prev_sales), 2)
    if prev_total > 0:
        change_pct = round(((total - prev_total) / prev_total) * 100, 1)
    elif total > 0:
        change_pct = 100.0
    else:
        change_pct = None

    series = _bucket_series(period, start, end, cur_orders)
    peak = _peak_window(series, period)
    order_ids = [int(o.id) for o in cur_sales if o.id is not None]
    top_products, categories, _ = _line_totals(session, order_ids)
    gst_amount = round(sum(float(o.gst_amount or 0) for o in cur_sales), 2)
    delivery_fee = round(sum(float(o.delivery_fee or 0) for o in cur_sales), 2)
    delivered = sum(1 for o in cur_sales if o.status == OrderStatus.DELIVERED)
    cancelled = [o for o in cur_orders if o.status in _CANCELLED]
    returns_amount = round(sum(float(o.final_amount or 0) for o in cancelled), 2)

    from app.services import sell as sell_ops

    try:
        catalog_rows = sell_ops.list_my_products(session, user)
    except Exception:
        catalog_rows = []
    catalog = [
        {
            "id": p.id,
            "name": p.name,
            "stock_qty": int(p.stock_qty or 0),
            "low_stock_threshold": int(p.low_stock_threshold or 5),
        }
        for p in catalog_rows
    ]
    low_stock = [
        {
            "product_id": p["id"],
            "name": p["name"],
            "stock_qty": p["stock_qty"],
        }
        for p in catalog
        if p["stock_qty"] <= p["low_stock_threshold"]
    ][:12]

    compare_label = {"daily": "vs Yesterday", "weekly": "vs Last week", "monthly": "vs Last month"}[period]
    granularity = {"daily": "By Hour", "weekly": "By Day", "monthly": "By Day"}[period]

    insights = _insights(
        total=total,
        prev_total=prev_total,
        change_pct=change_pct,
        peak=peak,
        top_products=top_products,
        low_stock=low_stock,
    )

    out = {
        "period": period,
        "anchor": day.isoformat(),
        "label": label,
        "granularity": granularity,
        "total_sales": total,
        "order_count": len(cur_sales),
        "prev_total": prev_total,
        "change_pct": change_pct,
        "compare_label": compare_label,
        "series": series,
        "peak": peak,
        "top_products": top_products,
        "categories": categories,
        "gst": {
            "collected": gst_amount,
            "order_count": len(cur_sales),
            "avg_per_order": round(gst_amount / len(cur_sales), 2) if cur_sales else 0,
        },
        "returns": {
            "count": len(cancelled),
            "amount": returns_amount,
        },
        "delivery": {
            "delivered": delivered,
            "fees": delivery_fee,
            "pending": sum(
                1
                for o in cur_sales
                if o.status
                in (
                    OrderStatus.PLACED,
                    OrderStatus.ACCEPTED,
                    OrderStatus.PREPARING,
                    OrderStatus.PACKED,
                    OrderStatus.OUT_FOR_DELIVERY,
                )
            ),
        },
        "inventory": {
            "sku_count": len(catalog),
            "low_stock_count": len(low_stock),
            "low_stock": low_stock,
        },
        "insights": insights,
        "reports": [
            {"id": "products", "title": "Product Sales", "subtitle": "Top performing products", "icon": "products"},
            {"id": "categories", "title": "Category Sales", "subtitle": "Sales by product categories", "icon": "week"},
            {"id": "gst", "title": "GST Report", "subtitle": "Tax collected & summary", "icon": "doc"},
            {"id": "returns", "title": "Returns", "subtitle": "Returned orders & amount", "icon": "bag"},
            {"id": "delivery", "title": "Delivery", "subtitle": "Delivery performance & insights", "icon": "truck"},
            {"id": "inventory", "title": "Inventory", "subtitle": "Stock status & alerts", "icon": "stock"},
        ],
    }
    logger.info("analytics shop=%s period=%s total=%.2f", user.id, period, total)
    return out


# ponytail: period math self-check
if __name__ == "__main__":
    s, e, ps, pe, lab = _period_bounds("daily", date(2025, 5, 20))
    assert (e - s).days == 1 and (s - ps).days == 1
    s, e, ps, pe, lab = _period_bounds("weekly", date(2025, 5, 20))
    assert (e - s).days == 7
    print("ok", lab)
