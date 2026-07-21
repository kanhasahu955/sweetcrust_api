"""Customer catalog — home feed, products, favorites, reviews."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func as sa_func
from sqlmodel import Session, col, func, or_, select

from app.models.catalog import (
    Category,
    Favorite,
    Product,
    ProductImage,
    ProductReview,
    RecentlyViewed,
)
from app.models.ops import Banner
from app.schemas.catalog import ProductListQuery
from package.common.errors import NotFoundError
from package.logger import get_logger
from package.redis import redis_get, redis_set
from package.redis.client import redis_delete_prefix

logger = get_logger(__name__)

HOME_FEED_TTL = 45
HOME_FEED_PREFIX = "catalog:home_feed"
CATEGORIES_KEY = "catalog:categories"


def invalidate_catalog_cache() -> None:
    redis_delete_prefix(HOME_FEED_PREFIX)
    redis_delete_prefix(CATEGORIES_KEY)


def _dump(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def _list_categories(session: Session, *, active_only: bool = True) -> list[Category]:
    q = select(Category)
    if active_only:
        q = q.where(Category.is_active == True)  # noqa: E712
    return list(session.exec(q.order_by(Category.display_order, Category.name)).all())


def _list_filtered(session: Session, query: ProductListQuery) -> tuple[list[Product], int]:
    stmt = select(Product).where(Product.is_active == True, Product.is_draft == False)  # noqa: E712
    if query.category_id:
        stmt = stmt.where(Product.category_id == query.category_id)
    if query.brand_name:
        stmt = stmt.where(sa_func.lower(Product.brand_name) == query.brand_name.lower().strip())
    if query.supplier_user_id:
        stmt = stmt.where(Product.supplier_user_id == query.supplier_user_id)
    if query.q:
        like = f"%{query.q.lower()}%"
        stmt = stmt.where(
            or_(
                sa_func.lower(Product.name).like(like),
                sa_func.lower(Product.short_description).like(like),
                sa_func.lower(Product.brand_name).like(like),
            )
        )
    if query.min_price is not None:
        stmt = stmt.where(Product.selling_price >= query.min_price)
    if query.max_price is not None:
        stmt = stmt.where(Product.selling_price <= query.max_price)
    if query.flavor:
        stmt = stmt.where(Product.flavor == query.flavor)
    if query.weight:
        stmt = stmt.where(Product.weight == query.weight)
    if query.eggless is not None:
        stmt = stmt.where(Product.is_eggless == query.eggless)
    if query.sugar_free is not None:
        stmt = stmt.where(Product.is_sugar_free == query.sugar_free)
    if query.min_rating is not None:
        stmt = stmt.where(Product.rating >= query.min_rating)
    if query.same_day is not None:
        stmt = stmt.where(Product.same_day_delivery == query.same_day)
    if query.in_stock:
        stmt = stmt.where(Product.stock_qty > 0)
    if query.offers:
        stmt = stmt.where(Product.discount_percent > 0)

    sort_map = {
        "popular": Product.sales_count.desc(),
        "price_asc": Product.selling_price.asc(),
        "price_desc": Product.selling_price.desc(),
        "newest": Product.created_at.desc(),
        "rating": Product.rating.desc(),
        "fastest": Product.estimated_delivery_mins.asc(),
    }
    stmt = stmt.order_by(sort_map.get(query.sort, Product.sales_count.desc()))
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    items = list(
        session.exec(stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)).all()
    )
    return items, total


def _flagged(session: Session, flag: str, *, limit: int = 10) -> list[Product]:
    attr = getattr(Product, flag, None)
    if attr is None:
        return []
    return list(
        session.exec(
            select(Product).where(attr == True, Product.is_active == True).limit(limit)  # noqa: E712
        ).all()
    )


def _top_rated(session: Session, *, limit: int = 10) -> list[Product]:
    return list(
        session.exec(
            select(Product)
            .where(Product.is_active == True)  # noqa: E712
            .order_by(Product.rating.desc())
            .limit(limit)
        ).all()
    )


def _recently_viewed(session: Session, user_id: int, *, limit: int = 10) -> list[Product]:
    recent_ids = session.exec(
        select(RecentlyViewed.product_id)
        .where(RecentlyViewed.user_id == user_id)
        .order_by(RecentlyViewed.viewed_at.desc())
        .limit(limit)
    ).all()
    if not recent_ids:
        return []
    return list(session.exec(select(Product).where(col(Product.id).in_(list(recent_ids)))).all())


def list_categories(session: Session, active_only: bool = True) -> list[Category] | list[dict]:
    cache_key = f"{CATEGORIES_KEY}:{int(active_only)}"
    cached = redis_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass
    categories = _list_categories(session, active_only=active_only)
    redis_set(cache_key, json.dumps(_dump(categories)), HOME_FEED_TTL)
    return categories


def list_products(session: Session, query: ProductListQuery) -> dict:
    items, total = _list_filtered(session, query)
    return {
        "items": items,
        "total": total,
        "page": query.page,
        "page_size": query.page_size,
        "has_more": query.page * query.page_size < total,
    }


def get_product(session: Session, product_id: int, user_id: int | None = None) -> Product:
    product = session.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    if user_id:
        session.add(RecentlyViewed(user_id=user_id, product_id=product_id))
        session.commit()
    return product


def product_detail(session: Session, product_id: int, user_id: int | None = None) -> dict:
    p = get_product(session, product_id, user_id)
    images = list(session.exec(select(ProductImage).where(ProductImage.product_id == product_id)).all())
    reviews = list(
        session.exec(select(ProductReview).where(ProductReview.product_id == product_id).limit(20)).all()
    )
    similar = list(
        session.exec(
            select(Product)
            .where(
                Product.category_id == p.category_id,
                Product.id != p.id,
                Product.is_active == True,  # noqa: E712
            )
            .limit(6)
        ).all()
    )
    return {
        "product": p,
        "images": images,
        "reviews": reviews,
        "similar": similar,
        "frequently_bought": similar[:3],
    }


def toggle_favorite(session: Session, user_id: int, product_id: int) -> dict:
    existing = session.exec(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.product_id == product_id)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
        return {"favorited": False}
    session.add(Favorite(user_id=user_id, product_id=product_id))
    session.commit()
    return {"favorited": True}


def add_review(
    session: Session,
    user_id: int,
    product_id: int,
    rating: int,
    comment: str | None,
    order_id: int | None,
) -> ProductReview:
    review = ProductReview(
        user_id=user_id,
        product_id=product_id,
        rating=rating,
        comment=comment,
        order_id=order_id,
    )
    session.add(review)
    product = session.get(Product, product_id)
    if product:
        total = product.rating * product.review_count + rating
        product.review_count += 1
        product.rating = round(total / product.review_count, 2)
        session.add(product)
    session.commit()
    session.refresh(review)
    invalidate_catalog_cache()
    return review


def home_feed(session: Session, user_id: int | None = None) -> dict:
    cache_key = f"{HOME_FEED_PREFIX}:{user_id or 0}"
    cached = redis_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    feed = {
        "categories": _list_categories(session),
        "banners": list(
            session.exec(select(Banner).where(Banner.is_active == True).order_by(Banner.sort_order)).all()  # noqa: E712
        ),
        "bestsellers": _flagged(session, "is_bestseller"),
        "freshly_baked": _flagged(session, "is_freshly_baked"),
        "trending": _flagged(session, "is_trending"),
        "festival_offers": _flagged(session, "is_festival"),
        "recommended": _top_rated(session),
        "recently_viewed": _recently_viewed(session, user_id) if user_id else [],
        "customized_cake_banner": {
            "title": "Design your dream cake",
            "subtitle": "Upload a reference photo & get a custom quotation",
            "cta": "Start Custom Cake",
        },
    }
    redis_set(cache_key, json.dumps(_dump(feed)), HOME_FEED_TTL)
    return feed
