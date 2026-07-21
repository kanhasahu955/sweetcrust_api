"""Customer catalog routes — gateway → catalog :8002."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import CurrentUser, OptionalUser, SessionDep
from app.services import products as product_ops
from app.schemas.catalog import ProductListQuery, ReviewIn
from package.common.schemas import ok
from package.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/customer", tags=["customer"])


@router.get("/home")
def home(session: SessionDep, user: OptionalUser):
    return ok(product_ops.home_feed(session, user.id if user else None))


@router.get("/categories")
def categories(session: SessionDep):
    return ok(product_ops.list_categories(session))


@router.get("/products")
def products(
    session: SessionDep,
    category_id: int | None = None,
    brand_name: str | None = None,
    supplier_user_id: int | None = None,
    q: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    flavor: str | None = None,
    weight: str | None = None,
    eggless: bool | None = None,
    sugar_free: bool | None = None,
    min_rating: float | None = None,
    same_day: bool | None = None,
    in_stock: bool | None = None,
    offers: bool | None = None,
    sort: str = "popular",
    page: int = 1,
    page_size: int = 20,
):
    query = ProductListQuery(
        category_id=category_id,
        brand_name=brand_name,
        supplier_user_id=supplier_user_id,
        q=q,
        min_price=min_price,
        max_price=max_price,
        flavor=flavor,
        weight=weight,
        eggless=eggless,
        sugar_free=sugar_free,
        min_rating=min_rating,
        same_day=same_day,
        in_stock=in_stock,
        offers=offers,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return ok(product_ops.list_products(session, query))


@router.get("/products/{product_id}")
def product_detail(product_id: int, session: SessionDep, user: OptionalUser):
    return ok(product_ops.product_detail(session, product_id, user.id if user else None))


@router.post("/products/{product_id}/favorite")
def favorite(product_id: int, session: SessionDep, user: CurrentUser):
    return ok(product_ops.toggle_favorite(session, user.id, product_id))


@router.post("/products/{product_id}/reviews")
def review(product_id: int, body: ReviewIn, session: SessionDep, user: CurrentUser):
    return ok(
        product_ops.add_review(session, user.id, product_id, body.rating, body.comment, body.order_id)
    )
