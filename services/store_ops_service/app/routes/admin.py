"""Admin P0 routes — paths match monolith / gateway catch-all."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Body, Query
from app.deps import AdminUser, AsyncSessionDep
from app.services import dashboard as dash_ops
from app.services import delivery as delivery_ops
from app.services import misc as misc_ops
from app.services import orders as order_ops
from app.services import products as product_ops
from app.services import settings_ops
from app.services import shops as shop_ops
from app.services import credit as credit_ops
from app.services import purchases as purchase_ops
from app.services import billing as billing_ops
from app.services import sell as sell_ops
from app.services import units as unit_ops
from app.schemas.admin import BannerIn, CategoryIn, CollectIn, CouponIn, CustomCakeAdminIn, DeliveryAssignIn, DeliveryPersonIn, DeliveryPersonPatchIn, MessageIn, OrderStatusUpdateIn, ProductIn, ProductPatchIn, ReturnAdminIn, SettingsUpdateIn, ShopCreateIn, ShopPatchIn, StockUpdateIn, SupplierPayIn, SupplierPurchaseIn, SupplierRazorpayCreateIn, SupplierRazorpayVerifyIn
from package.common.schemas import APIModel, ok
from package.logger import get_logger
from app.controllers.store_ops_async import StoreOpsController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await StoreOpsController(session).call(fn, *args, **kwargs)

logger = get_logger(__name__)
router = APIRouter(prefix='/admin', tags=['admin'])

class LocationIn(APIModel):
    lat: float
    lng: float
    eta_minutes: Optional[int] = None

@router.get('/dashboard')
async def get_dashboard(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, dash_ops.dashboard))

@router.get('/orders')
async def get_orders(session: AsyncSessionDep, _: AdminUser, status_group: Optional[str]=None):
    return ok(await _domain(session, order_ops.list_orders, status_group))

@router.get('/orders/{order_id}')
async def get_order(order_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, order_ops.order_detail, order_id))

@router.patch('/orders/{order_id}/status')
async def patch_order_status(order_id: int, body: OrderStatusUpdateIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, order_ops.update_order_status, order_id, body.status, admin.id, body.note, body.delivery_person_id))

@router.post('/orders/{order_id}/assign-delivery')
async def assign_delivery(order_id: int, body: DeliveryAssignIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, order_ops.assign_delivery, order_id, body.delivery_person_id, admin.id))

@router.post('/orders/{order_id}/offer-delivery')
async def offer_delivery(order_id: int, body: DeliveryAssignIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, order_ops.offer_delivery, order_id, body.delivery_person_id, admin.id))

@router.post('/orders/{order_id}/invoice')
async def post_invoice(order_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, order_ops.make_invoice, order_id))

@router.post('/orders/{order_id}/payment-link')
async def post_payment_link(order_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, order_ops.payment_link, order_id))

@router.get('/products')
async def get_products(
    session: AsyncSessionDep,
    _: AdminUser,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category_id: Optional[int] = Query(None, ge=1),
    supplier_user_id: Optional[int] = Query(None, ge=1),
):
    return ok(
        await _domain(
            session,
            product_ops.list_products,
            q=q,
            page=page,
            page_size=page_size,
            category_id=category_id,
            supplier_user_id=supplier_user_id,
        )
    )

@router.post('/products')
async def post_product(body: ProductIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, product_ops.create_product, body, admin.id))

@router.patch('/products/{product_id}')
async def patch_product(product_id: int, body: ProductPatchIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, product_ops.update_product, product_id, body.model_dump(exclude_unset=True)))

@router.delete('/products/{product_id}')
async def delete_product(product_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, product_ops.soft_delete_product, product_id))

@router.post('/products/{product_id}/duplicate')
async def duplicate_product(product_id: int, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, product_ops.duplicate_product, product_id, admin.id))

@router.patch('/products/{product_id}/stock')
async def patch_stock(product_id: int, body: StockUpdateIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, product_ops.update_stock, product_id, body.stock_qty, body.reason, body.note, admin.id))

@router.post('/products/ai-upload/publish')
async def publish_ai(session: AsyncSessionDep, admin: AdminUser, body: dict=Body(...)):
    return ok(await _domain(session, product_ops.publish_ai_product, body, admin.id))

@router.get('/units')
async def get_units(_: AdminUser):
    return ok(unit_ops.list_units())


@router.get('/categories')
async def get_categories(session: AsyncSessionDep, _: AdminUser, active_only: bool=False):
    return ok(await _domain(session, product_ops.list_categories, active_only=active_only))

@router.post('/categories')
async def post_category(body: CategoryIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, product_ops.upsert_category, body.model_dump()))

@router.patch('/categories/{category_id}')
async def patch_category(category_id: int, body: CategoryIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, product_ops.update_category, category_id, body.model_dump(exclude_unset=True)))

@router.delete('/categories/{category_id}')
async def delete_category(category_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, product_ops.delete_category, category_id))

@router.get('/inventory')
async def get_inventory(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.inventory))

@router.get('/delivery/persons')
async def get_persons(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, delivery_ops.list_persons))

@router.post('/delivery/persons')
async def post_person(body: DeliveryPersonIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, delivery_ops.create_person, body))

@router.patch('/delivery/persons/{person_id}')
async def patch_person(person_id: int, body: DeliveryPersonPatchIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, delivery_ops.patch_person, person_id, body))

@router.get('/delivery/live')
async def get_live(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, delivery_ops.live))

@router.post('/delivery/{order_id}/location')
async def post_location(order_id: int, body: LocationIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, delivery_ops.update_location, order_id, body.lat, body.lng, body.eta_minutes))

@router.get('/payments')
async def get_payments(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.list_payments))

@router.post('/payments/{payment_id}/refund')
async def post_refund(payment_id: int, session: AsyncSessionDep, _: AdminUser, amount: Optional[float]=None):
    return ok(await _domain(session, misc_ops.refund_payment, payment_id, amount))

@router.get('/coupons')
async def get_coupons(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.list_coupons))

@router.post('/coupons')
async def post_coupon(body: CouponIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.create_coupon, body))

@router.get('/returns')
async def get_returns(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.list_returns))

@router.patch('/returns/{return_id}')
async def patch_return(return_id: int, body: ReturnAdminIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.patch_return, return_id, body))

@router.get('/chats')
async def get_chats(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.list_chats))

@router.get('/chats/{conversation_id}/messages')
async def get_chat_messages(conversation_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.chat_messages, conversation_id))

@router.post('/chats/{conversation_id}/messages')
async def post_chat_message(conversation_id: int, body: MessageIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, misc_ops.send_chat, conversation_id, admin, body))

@router.post('/chats/{conversation_id}/takeover')
async def post_takeover(conversation_id: int, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, misc_ops.takeover, conversation_id, admin))

@router.get('/tickets')
async def get_tickets(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.list_tickets))

@router.get('/shops')
async def get_shops(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, shop_ops.list_shops))

@router.post('/shops')
async def post_shop(body: ShopCreateIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, shop_ops.create_shop, body))

@router.post('/shops/{retailer_user_id}/approve')
async def approve_shop(retailer_user_id: int, session: AsyncSessionDep, _: AdminUser, payload: Optional[dict]=Body(default=None)):
    return ok(await _domain(session, shop_ops.approve_shop, retailer_user_id, payload))

@router.post('/shops/{retailer_user_id}/reject')
async def reject_shop(retailer_user_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, shop_ops.reject_shop, retailer_user_id))


class SellSubIn(APIModel):
    status: str = "approved"


@router.post('/shops/{retailer_user_id}/sell-subscription')
async def set_sell_subscription(retailer_user_id: int, body: SellSubIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, shop_ops.set_sell_subscription, retailer_user_id, body.status))

@router.patch('/shops/{retailer_user_id}')
async def patch_shop(retailer_user_id: int, body: ShopPatchIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, shop_ops.patch_shop, retailer_user_id, body))

@router.get('/shops/{retailer_user_id}/ledger')
async def get_ledger(retailer_user_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, credit_ops.list_ledger, retailer_user_id))

@router.get('/shops/{retailer_user_id}/account')
async def get_shop_account(retailer_user_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, billing_ops.admin_shop_account, retailer_user_id))

@router.get('/shops/{retailer_user_id}/catalog')
async def get_shop_catalog(retailer_user_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, sell_ops.admin_shop_catalog, retailer_user_id))

class ShopToggleIn(APIModel):
    is_active: bool = True

@router.patch('/shops/{retailer_user_id}/banners/{banner_id}')
async def patch_shop_banner(
    retailer_user_id: int, banner_id: int, body: ShopToggleIn, session: AsyncSessionDep, _: AdminUser
):
    return ok(
        await _domain(session, sell_ops.admin_set_shop_banner_active, banner_id, retailer_user_id, body.is_active)
    )

@router.patch('/shops/{retailer_user_id}/coupons/{coupon_id}')
async def patch_shop_coupon(
    retailer_user_id: int, coupon_id: int, body: ShopToggleIn, session: AsyncSessionDep, _: AdminUser
):
    return ok(
        await _domain(session, sell_ops.admin_set_shop_coupon_active, coupon_id, retailer_user_id, body.is_active)
    )

@router.post('/shops/{retailer_user_id}/collect')
async def post_collect(retailer_user_id: int, body: CollectIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, credit_ops.credit_payment, retailer_user_id, body.amount, note=body.note, method=body.method, created_by=admin.id))

@router.get('/purchases')
async def get_purchases(session: AsyncSessionDep, _: AdminUser, supplier_user_id: Optional[int]=None):
    return ok(await _domain(session, purchase_ops.list_purchases, supplier_user_id))

@router.post('/purchases')
async def post_purchase(body: SupplierPurchaseIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, purchase_ops.create_purchase, supplier_user_id=body.supplier_user_id, product_id=body.product_id, qty=body.qty, unit_cost=body.unit_cost, note=body.note, created_by=admin.id, mark_paid=body.mark_paid, pay_method=body.pay_method, instant_receive=body.instant_receive))

@router.post('/purchases/{purchase_id}/pay')
async def post_pay_purchase(purchase_id: int, body: SupplierPayIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, purchase_ops.pay_purchase, purchase_id, amount=body.amount, pay_method=body.pay_method, note=body.note, created_by=admin.id))

@router.post('/purchases/{purchase_id}/razorpay/create')
async def post_purchase_razorpay_create(purchase_id: int, body: SupplierRazorpayCreateIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, purchase_ops.create_razorpay_pay, purchase_id, amount=body.amount, created_by=admin.id))

@router.post('/purchases/{purchase_id}/razorpay/verify')
async def post_purchase_razorpay_verify(purchase_id: int, body: SupplierRazorpayVerifyIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(
        session,
        purchase_ops.verify_razorpay_pay,
        purchase_id,
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        razorpay_signature=body.razorpay_signature,
        amount=body.amount,
        created_by=admin.id,
    ))

@router.get('/customers')
async def get_customers(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.customers))

@router.get('/customers/{customer_id}/presence')
async def get_customer_presence(customer_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.customer_presence, customer_id))

@router.get('/reports')
async def get_reports(session: AsyncSessionDep, _: AdminUser, period: str='weekly'):
    return ok(await _domain(session, misc_ops.reports, period))

@router.get('/settings')
async def get_settings(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, settings_ops.get_settings_row))

@router.get('/integrations/check')
def get_integrations_check(_: AdminUser):
    return ok(misc_ops.integrations_check())

@router.patch('/settings')
async def patch_settings(body: SettingsUpdateIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, settings_ops.patch_settings, body))

@router.get('/custom-cakes')
async def get_custom_cakes(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.list_custom_cakes))

@router.patch('/custom-cakes/{req_id}')
async def patch_custom_cake(req_id: int, body: CustomCakeAdminIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.patch_custom_cake, req_id, body.status, body.quoted_price))

@router.get('/notifications')
async def get_notifications(session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, misc_ops.list_notifications, admin.id))

@router.post('/notifications/read')
async def read_notifications(session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, misc_ops.mark_notifications_read, admin.id))

@router.get('/banners')
async def get_banners(
    session: AsyncSessionDep,
    _: AdminUser,
    shop_user_id: Optional[int] = Query(None, ge=1),
):
    return ok(await _domain(session, misc_ops.list_banners, shop_user_id=shop_user_id))

@router.post('/banners')
async def post_banner(body: BannerIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, misc_ops.create_banner, body))
