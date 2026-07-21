"""Search HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import products as product_ops

def _query(q, category_id, page, page_size, min_price=None, max_price=None):
    try:
        from app.schemas.catalog import ProductListQuery
        return ProductListQuery(q=q, category_id=category_id, page=page, page_size=page_size,
                                min_price=min_price, max_price=max_price)
    except Exception:
        from types import SimpleNamespace
        return SimpleNamespace(q=q, category_id=category_id, page=page, page_size=page_size,
                               sort=None, filters=None, min_price=min_price, max_price=max_price,
                               flavor=None, weight=None, eggless=None, sugar_free=None,
                               min_rating=None, same_day=None)

def search(session: Session, q=None, category_id=None, page=1, page_size=20, min_price=None, max_price=None):
    return product_ops.list_products(session, _query(q, category_id, page, page_size, min_price, max_price))

def suggest(session: Session, q: str, limit: int = 8):
    data = search(session, q=q, page=1, page_size=limit)
    items = data.get("items") if isinstance(data, dict) else data
    out = []
    for p in items or []:
        out.append({"id": getattr(p, "id", None), "name": getattr(p, "name", None),
                    "slug": getattr(p, "slug", None), "cover_image_url": getattr(p, "cover_image_url", None)})
    return {"suggestions": out, "q": q}
