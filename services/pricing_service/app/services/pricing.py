"""Pricing domain — customer/shop unit prices and admin edits."""
from __future__ import annotations
from sqlmodel import Session
from app.repositories import products as product_repo
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now

def customer_unit_price(product) -> float:
    if product.customer_price is not None:
        return float(product.customer_price)
    return float(product.selling_price or 0)

def shop_unit_price(product) -> float:
    if product.shop_price is not None:
        return float(product.shop_price)
    return float(product.selling_price or 0)

def quote(session: Session, product_id: int, channel: str = "customer") -> dict:
    p = product_repo.get(session, product_id)
    if not p:
        raise NotFoundError("Product not found")
    ch = (channel or "customer").lower()
    unit = shop_unit_price(p) if ch in ("shop", "retailer", "b2b") else customer_unit_price(p)
    return {
        "product_id": p.id, "name": p.name, "channel": ch, "unit_price": unit,
        "selling_price": float(p.selling_price or 0), "customer_price": p.customer_price,
        "shop_price": p.shop_price, "original_price": p.original_price,
        "purchase_cost": p.purchase_cost,
        "margin": round(unit - float(p.purchase_cost or 0), 2) if p.purchase_cost is not None else None,
    }

def quote_bulk(session: Session, product_ids: list[int], channel: str = "customer") -> list[dict]:
    return [quote(session, pid, channel) for pid in product_ids]

def update_prices(session: Session, product_id: int, data: dict):
    p = product_repo.get(session, product_id)
    if not p:
        raise NotFoundError("Product not found")
    allowed = {"selling_price", "customer_price", "shop_price", "original_price", "purchase_cost", "discount_percent", "gst_rate"}
    for k, v in data.items():
        if k not in allowed:
            continue
        if v is not None and (k.endswith("price") or k == "purchase_cost") and float(v) < 0:
            raise BadRequestError(f"{k} must be >= 0")
        setattr(p, k, v)
    p.updated_at = utc_now()
    return product_repo.save(session, p)

def estimate_custom_cake(weight: str, budget_max: float | None = None) -> dict:
    base = {"0.5kg": 499, "1kg": 799, "1.5kg": 1099, "2kg": 1399}.get((weight or "1kg").lower(), 799)
    if budget_max is not None:
        base = min(base, float(budget_max))
    return {"weight": weight, "estimated_price": base}

def list_priced(session: Session, page: int = 1, page_size: int = 50) -> dict:
    rows = product_repo.list_all(session)
    start = max(0, (page - 1) * page_size)
    items = [{
        "id": p.id, "name": p.name, "brand_name": getattr(p, "brand_name", None),
        "selling_price": p.selling_price,
        "customer_price": p.customer_price, "shop_price": p.shop_price,
        "purchase_cost": p.purchase_cost, "customer_unit": customer_unit_price(p),
        "shop_unit": shop_unit_price(p),
    } for p in rows[start:start + page_size]]
    return {"items": items, "total": len(rows), "page": page}
