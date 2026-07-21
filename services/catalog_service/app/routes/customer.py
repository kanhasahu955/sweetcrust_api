"""Customer catalog routes — gateway → catalog :8002."""
from __future__ import annotations
from fastapi import APIRouter
from app.deps import CurrentUser, OptionalUser, AsyncSessionDep
from app.services import products as product_ops
from app.services import shops as shop_ops
from app.services import settings_public as settings_ops
from app.schemas.catalog import ProductListQuery, ReviewIn
from package.common.schemas import ok
from package.logger import get_logger
from app.controllers.catalog_async import CatalogController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await CatalogController(session).call(fn, *args, **kwargs)

logger = get_logger(__name__)
router = APIRouter(prefix='/customer', tags=['customer'])

@router.get('/home')
async def home(session: AsyncSessionDep, user: OptionalUser):
    return ok(await _domain(session, product_ops.home_feed, user.id if user else None))

@router.get('/settings')
async def settings(session: AsyncSessionDep):
    """Bakery phone, delivery slots, charges — for checkout / PDP support."""
    return ok(await _domain(session, settings_ops.public_settings))

@router.get('/categories')
async def categories(session: AsyncSessionDep):
    return ok(await _domain(session, product_ops.list_categories))

@router.get('/brands')
async def brands(session: AsyncSessionDep):
    return ok(await _domain(session, product_ops.list_brands))

@router.get('/shops')
async def shops(session: AsyncSessionDep):
    return ok(await _domain(session, shop_ops.list_shops))

@router.get('/shops/{shop_user_id}')
async def shop_detail(shop_user_id: int, session: AsyncSessionDep):
    return ok(await _domain(session, shop_ops.shop_detail, shop_user_id))

@router.get('/products')
async def products(
    session: AsyncSessionDep,
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
    sort: str = 'popular',
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
    return ok(await _domain(session, product_ops.list_products, query))

@router.get('/products/{product_id}')
async def product_detail(product_id: int, session: AsyncSessionDep, user: OptionalUser):
    return ok(await _domain(session, product_ops.product_detail, product_id, user.id if user else None))

@router.post('/products/{product_id}/favorite')
async def favorite(product_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, product_ops.toggle_favorite, user.id, product_id))

@router.post('/products/{product_id}/reviews')
async def review(product_id: int, body: ReviewIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, product_ops.add_review, user.id, product_id, body.rating, body.comment, body.order_id))
