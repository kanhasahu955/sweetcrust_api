from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Category, Product, StockMovement
from app.models.enums import StockStatus
from app.schemas.admin import CategoryIn, ProductIn
from package.common.errors import NotFoundError
from package.common.utils import slugify, stock_status_for, utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def list_products(session: Session, *, q: str | None = None, page: int = 1, page_size: int = 50):
    stmt = select(Product).order_by(Product.updated_at.desc())
    rows = list(session.exec(stmt).all())
    if q:
        ql = q.lower()
        rows = [p for p in rows if ql in (p.name or "").lower()]
    start = max(0, (page - 1) * page_size)
    return {"items": rows[start : start + page_size], "total": len(rows), "page": page}


def create_product(session: Session, body: ProductIn, admin_id: int | None = None) -> Product:
    base = slugify(body.name) or "product"
    slug = base
    i = 1
    while session.exec(select(Product).where(Product.slug == slug)).first():
        slug = f"{base}-{i}"
        i += 1
    status = stock_status_for(body.stock_qty)
    p = Product(
        category_id=body.category_id,
        name=body.name,
        slug=slug,
        short_description=body.short_description,
        description=body.description,
        ingredients=body.ingredients,
        allergens=body.allergens,
        flavor=body.flavor,
        weight=body.weight,
        selling_price=body.selling_price,
        customer_price=body.customer_price,
        shop_price=body.shop_price,
        original_price=body.original_price,
        gst_rate=body.gst_rate,
        stock_qty=body.stock_qty,
        stock_status=StockStatus(status),
        is_eggless=body.is_eggless,
        is_sugar_free=body.is_sugar_free,
        preparation_minutes=body.preparation_minutes,
        shelf_life_hours=body.shelf_life_hours,
        storage_instructions=body.storage_instructions,
        tags=body.tags,
        filters=body.filters,
        cover_image_url=body.cover_image_url,
        is_draft=body.is_draft,
        is_active=body.is_active,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    logger.info("product created id=%s", p.id)
    return p


def update_product(session: Session, product_id: int, data: dict) -> Product:
    p = session.get(Product, product_id)
    if not p:
        raise NotFoundError("Product not found")
    for k, v in data.items():
        if hasattr(p, k):
            setattr(p, k, v)
    if "stock_qty" in data:
        p.stock_status = StockStatus(stock_status_for(int(data["stock_qty"])))
    p.updated_at = utc_now()
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def soft_delete_product(session: Session, product_id: int) -> dict:
    p = session.get(Product, product_id)
    if p:
        p.is_active = False
        p.updated_at = utc_now()
        session.add(p)
        session.commit()
    return {"message": "disabled"}


def duplicate_product(session: Session, product_id: int, admin_id: int | None = None) -> Product:
    p = session.get(Product, product_id)
    if not p:
        raise NotFoundError("Product not found")
    data = ProductIn(
        category_id=p.category_id,
        name=f"{p.name} (Copy)",
        short_description=p.short_description,
        description=p.description,
        selling_price=p.selling_price,
        original_price=p.original_price,
        stock_qty=p.stock_qty,
        is_eggless=p.is_eggless,
        cover_image_url=p.cover_image_url,
        tags=p.tags,
        filters=p.filters,
        is_draft=True,
    )
    return create_product(session, data, admin_id)


def update_stock(session: Session, product_id: int, stock_qty: int, reason: str, note: str | None, admin_id: int | None):
    p = session.get(Product, product_id)
    if not p:
        raise NotFoundError("Product not found")
    delta = stock_qty - (p.stock_qty or 0)
    p.stock_qty = stock_qty
    p.stock_status = StockStatus(stock_status_for(stock_qty))
    p.updated_at = utc_now()
    session.add(p)
    session.add(StockMovement(product_id=product_id, change_qty=delta, reason=reason, note=note, created_by=admin_id))
    session.commit()
    session.refresh(p)
    return p


def list_categories(session: Session, *, active_only: bool = False):
    stmt = select(Category).order_by(Category.display_order, Category.name)
    rows = list(session.exec(stmt).all())
    if active_only:
        rows = [c for c in rows if c.is_active]
    return rows


def upsert_category(session: Session, data: dict) -> Category:
    name = data["name"]
    slug = slugify(name)
    cat = session.exec(select(Category).where(Category.slug == slug)).first()
    if not cat:
        cat = Category(name=name, slug=slug)
    for k, v in data.items():
        if k != "name" and hasattr(cat, k):
            setattr(cat, k, v)
    cat.name = name
    cat.updated_at = utc_now()
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def publish_ai_product(session: Session, body: dict, admin_id: int) -> Product:
    s = body.get("suggestions") or body
    cat_name = s.get("category") or "Birthday Cakes"
    cat = session.exec(select(Category).where(Category.name == cat_name)).first()
    if not cat:
        cat = Category(name=cat_name, slug=slugify(cat_name))
        session.add(cat)
        session.commit()
        session.refresh(cat)
    product_in = ProductIn(
        category_id=cat.id,
        name=s.get("name") or s.get("title") or "New Product",
        short_description=s.get("short_description"),
        description=s.get("description"),
        ingredients=s.get("ingredients"),
        allergens=s.get("allergens"),
        flavor=s.get("flavor"),
        weight=s.get("weight"),
        selling_price=float(s.get("selling_price") or s.get("recommended_selling_price") or 299),
        original_price=s.get("original_price") or s.get("discount_price"),
        gst_rate=float(s.get("gst_rate") or 5),
        stock_qty=int(s.get("suggested_stock") or 10),
        is_eggless=bool(s.get("is_eggless") or s.get("eggless")),
        is_sugar_free=bool(s.get("sugar_free")),
        preparation_minutes=int(s.get("preparation_time") or 60),
        shelf_life_hours=s.get("shelf_life_hours"),
        storage_instructions=s.get("storage_instructions"),
        tags=s.get("tags") or s.get("keywords"),
        filters=s.get("filters"),
        cover_image_url=(body.get("cover_image") or (body.get("image_urls") or [None])[0]),
        is_draft=not body.get("publish", True),
        is_active=bool(body.get("publish", True)),
    )
    product = create_product(session, product_in, admin_id)
    quality = body.get("quality") or {}
    product.quality_score = quality.get("score")
    product.quality_suggestions = quality.get("suggestions")
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def update_category(session: Session, category_id: int, data: dict) -> Category:
    cat = session.get(Category, category_id)
    if not cat:
        raise NotFoundError("Category not found")
    if "name" in data and data["name"]:
        cat.name = data["name"]
        cat.slug = slugify(data["name"])
    for k, v in data.items():
        if k != "name" and hasattr(cat, k):
            setattr(cat, k, v)
    cat.updated_at = utc_now()
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def delete_category(session: Session, category_id: int) -> dict:
    cat = session.get(Category, category_id)
    if not cat:
        raise NotFoundError("Category not found")
    cat.is_active = False
    cat.updated_at = utc_now()
    session.add(cat)
    session.commit()
    return {"message": "disabled"}
