"""Temporary retailer BFF (non-AI) until commerce owns B2B."""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter
from app.deps import RetailerUser, AsyncSessionDep
from app.services import billing as billing_ops
from app.services import retailer_bff as r_ops
from app.services import sell as sell_ops
from app.services import supplier as supplier_ops
from app.schemas.admin import BulkOrderIn, CallbackIn, MessageIn, ProductRequestIn, RetailerProfilePatchIn
from package.common.schemas import APIModel, ok
from package.logger import get_logger
from app.controllers.store_ops_async import StoreOpsController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await StoreOpsController(session).call(fn, *args, **kwargs)

logger = get_logger(__name__)
router = APIRouter(prefix='/retailer', tags=['retailer'])

class PresenceIn(APIModel):
    online: bool = True


class SupplierProductPatchIn(APIModel):
    supplier_available_qty: Optional[int] = None
    purchase_cost: Optional[float] = None


class ShopProductIn(APIModel):
    category_id: int
    name: str
    selling_price: float = 0
    customer_price: Optional[float] = None
    shop_price: Optional[float] = None
    purchase_cost: Optional[float] = None
    stock_qty: int = 0
    short_description: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_active: bool = True


class ShopProductPatchIn(APIModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    selling_price: Optional[float] = None
    customer_price: Optional[float] = None
    shop_price: Optional[float] = None
    purchase_cost: Optional[float] = None
    stock_qty: Optional[int] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_active: Optional[bool] = None
    is_draft: Optional[bool] = None


class SalesStatusIn(APIModel):
    status: str
    note: Optional[str] = None

@router.get('/me')
async def get_me(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.me, user))

@router.patch('/me')
async def patch_me(body: RetailerProfilePatchIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.patch_me, user, body))

@router.post('/me/submit')
async def submit(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.submit, user))

@router.post('/presence')
async def presence(body: PresenceIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.presence, user, body.online))

@router.get('/catalog')
async def catalog(session: AsyncSessionDep, _: RetailerUser, brand_name: str | None = None):
    return ok(await _domain(session, r_ops.catalog, brand_name=brand_name))

@router.post('/products/request')
async def product_request(body: ProductRequestIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.request_product, user, {'image_urls': body.image_urls, 'cover_image': body.cover_image, 'suggestions': body.suggestions, 'notes': body.notes}))

@router.post('/orders')
async def create_order(body: BulkOrderIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(
        session,
        r_ops.create_bulk_order,
        user,
        [line.model_dump() for line in body.lines],
        body.note,
        pay_mode=body.pay_mode,
        paid_now=body.paid_now,
    ))

@router.get('/orders')
async def orders(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.my_orders, user))

@router.get('/orders/{order_id}')
async def order_detail(order_id: int, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.get_order, user, order_id))

@router.get('/chats')
async def chats(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.list_chats, user))

@router.post('/chats/support')
async def open_support(session: AsyncSessionDep, user: RetailerUser, ai: bool=False):
    return ok(await _domain(session, r_ops.open_support, user, ai=ai))

@router.get('/chats/{conversation_id}/messages')
async def messages(conversation_id: int, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.list_messages, conversation_id, user))

@router.post('/chats/{conversation_id}/messages')
async def send(conversation_id: int, body: MessageIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.send_message, conversation_id, user, body.content, body.message_type, body.media_url, body.metadata_json))

@router.post('/calls/callback')
async def request_callback(body: CallbackIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, r_ops.request_callback, user, body.note))


@router.get('/billing/summary')
async def billing_summary(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, billing_ops.summary, user))


@router.get('/billing/ledger')
async def billing_ledger(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, billing_ops.ledger, user))


@router.get('/billing/invoices')
async def billing_invoices(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, billing_ops.invoices, user))


@router.get('/billing/supplier-bills')
async def billing_supplier_bills(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, billing_ops.supplier_bills, user))


@router.get('/catalog/categories')
async def sell_categories(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, sell_ops.list_categories, user))


@router.get('/catalog/products')
async def sell_products(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, sell_ops.list_my_products, user))


@router.post('/catalog/products')
async def sell_create_product(body: ShopProductIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, sell_ops.create_my_product, user, body.model_dump()))


@router.patch('/catalog/products/{product_id}')
async def sell_patch_product(product_id: int, body: ShopProductPatchIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(
        await _domain(
            session,
            sell_ops.patch_my_product,
            user,
            product_id,
            body.model_dump(exclude_unset=True),
        )
    )


@router.get('/sales/orders')
async def sell_orders(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, sell_ops.list_sales_orders, user))


@router.patch('/sales/orders/{order_id}/status')
async def sell_order_status(order_id: int, body: SalesStatusIn, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, sell_ops.update_sales_status, user, order_id, body.status, body.note))


@router.get('/supplier/summary')
async def supplier_summary(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, supplier_ops.summary, user))


@router.get('/supplier/purchases')
async def supplier_purchases(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, supplier_ops.list_my_purchases, user))


@router.post('/supplier/purchases/{purchase_id}/accept')
async def supplier_accept(purchase_id: int, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, supplier_ops.accept, user, purchase_id))


@router.post('/supplier/purchases/{purchase_id}/reject')
async def supplier_reject(purchase_id: int, session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, supplier_ops.reject, user, purchase_id))


@router.get('/supplier/products')
async def supplier_products(session: AsyncSessionDep, user: RetailerUser):
    return ok(await _domain(session, supplier_ops.list_my_products, user))


@router.patch('/supplier/products/{product_id}')
async def supplier_patch_product(
    product_id: int, body: SupplierProductPatchIn, session: AsyncSessionDep, user: RetailerUser
):
    return ok(
        await _domain(
            session,
            supplier_ops.patch_my_product,
            user,
            product_id,
            supplier_available_qty=body.supplier_available_qty,
            purchase_cost=body.purchase_cost,
        )
    )
