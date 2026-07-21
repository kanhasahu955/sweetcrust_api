"""Admin P0 routes — paths match monolith / gateway catch-all."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Query

from app.deps import AdminUser, SessionDep
from app.services import dashboard as dash_ops
from app.services import delivery as delivery_ops
from app.services import misc as misc_ops
from app.services import orders as order_ops
from app.services import products as product_ops
from app.services import settings_ops
from app.services import shops as shop_ops
from app.services import credit as credit_ops
from app.services import purchases as purchase_ops
from app.schemas.admin import (
    BannerIn,
    CategoryIn,
    CollectIn,
    CouponIn,
    CustomCakeAdminIn,
    DeliveryAssignIn,
    DeliveryPersonIn,
    DeliveryPersonPatchIn,
    MessageIn,
    OrderStatusUpdateIn,
    ProductIn,
    ProductPatchIn,
    ReturnAdminIn,
    SettingsUpdateIn,
    ShopCreateIn,
    ShopPatchIn,
    StockUpdateIn,
    SupplierPayIn,
    SupplierPurchaseIn,
)
from package.common.schemas import APIModel, ok
from package.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class LocationIn(APIModel):
    lat: float
    lng: float
    eta_minutes: Optional[int] = None


@router.get("/dashboard")
def get_dashboard(session: SessionDep, _: AdminUser):
    return ok(dash_ops.dashboard(session))


@router.get("/orders")
def get_orders(session: SessionDep, _: AdminUser, status_group: Optional[str] = None):
    return ok(order_ops.list_orders(session, status_group))


@router.get("/orders/{order_id}")
def get_order(order_id: int, session: SessionDep, _: AdminUser):
    return ok(order_ops.order_detail(session, order_id))


@router.patch("/orders/{order_id}/status")
def patch_order_status(order_id: int, body: OrderStatusUpdateIn, session: SessionDep, admin: AdminUser):
    return ok(order_ops.update_order_status(session, order_id, body.status, admin.id, body.note, body.delivery_person_id))


@router.post("/orders/{order_id}/assign-delivery")
def assign_delivery(order_id: int, body: DeliveryAssignIn, session: SessionDep, admin: AdminUser):
    from app.models.enums import OrderStatus

    return ok(
        order_ops.update_order_status(
            session,
            order_id,
            OrderStatus.DELIVERY_ASSIGNED.value,
            admin.id,
            None,
            body.delivery_person_id,
        )
    )


@router.post("/orders/{order_id}/invoice")
def post_invoice(order_id: int, session: SessionDep, _: AdminUser):
    return ok(order_ops.make_invoice(session, order_id))


@router.post("/orders/{order_id}/payment-link")
def post_payment_link(order_id: int, session: SessionDep, _: AdminUser):
    return ok(order_ops.payment_link(session, order_id))


@router.get("/products")
def get_products(
    session: SessionDep,
    _: AdminUser,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return ok(product_ops.list_products(session, q=q, page=page, page_size=page_size))


@router.post("/products")
def post_product(body: ProductIn, session: SessionDep, admin: AdminUser):
    return ok(product_ops.create_product(session, body, admin.id))


@router.patch("/products/{product_id}")
def patch_product(product_id: int, body: ProductPatchIn, session: SessionDep, _: AdminUser):
    return ok(product_ops.update_product(session, product_id, body.model_dump(exclude_unset=True)))


@router.delete("/products/{product_id}")
def delete_product(product_id: int, session: SessionDep, _: AdminUser):
    return ok(product_ops.soft_delete_product(session, product_id))


@router.post("/products/{product_id}/duplicate")
def duplicate_product(product_id: int, session: SessionDep, admin: AdminUser):
    return ok(product_ops.duplicate_product(session, product_id, admin.id))


@router.patch("/products/{product_id}/stock")
def patch_stock(product_id: int, body: StockUpdateIn, session: SessionDep, admin: AdminUser):
    return ok(product_ops.update_stock(session, product_id, body.stock_qty, body.reason, body.note, admin.id))


@router.post("/products/ai-upload/publish")
def publish_ai(session: SessionDep, admin: AdminUser, body: dict = Body(...)):
    return ok(product_ops.publish_ai_product(session, body, admin.id))


@router.get("/categories")
def get_categories(session: SessionDep, _: AdminUser, active_only: bool = False):
    return ok(product_ops.list_categories(session, active_only=active_only))


@router.post("/categories")
def post_category(body: CategoryIn, session: SessionDep, _: AdminUser):
    return ok(product_ops.upsert_category(session, body.model_dump()))


@router.patch("/categories/{category_id}")
def patch_category(category_id: int, body: CategoryIn, session: SessionDep, _: AdminUser):
    return ok(product_ops.update_category(session, category_id, body.model_dump(exclude_unset=True)))


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, session: SessionDep, _: AdminUser):
    return ok(product_ops.delete_category(session, category_id))


@router.get("/inventory")
def get_inventory(session: SessionDep, _: AdminUser):
    return ok(misc_ops.inventory(session))


@router.get("/delivery/persons")
def get_persons(session: SessionDep, _: AdminUser):
    return ok(delivery_ops.list_persons(session))


@router.post("/delivery/persons")
def post_person(body: DeliveryPersonIn, session: SessionDep, _: AdminUser):
    return ok(delivery_ops.create_person(session, body))


@router.patch("/delivery/persons/{person_id}")
def patch_person(person_id: int, body: DeliveryPersonPatchIn, session: SessionDep, _: AdminUser):
    return ok(delivery_ops.patch_person(session, person_id, body))


@router.get("/delivery/live")
def get_live(session: SessionDep, _: AdminUser):
    return ok(delivery_ops.live(session))


@router.post("/delivery/{order_id}/location")
def post_location(order_id: int, body: LocationIn, session: SessionDep, _: AdminUser):
    return ok(delivery_ops.update_location(session, order_id, body.lat, body.lng, body.eta_minutes))


@router.get("/payments")
def get_payments(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_payments(session))


@router.post("/payments/{payment_id}/refund")
def post_refund(payment_id: int, session: SessionDep, _: AdminUser, amount: Optional[float] = None):
    return ok(misc_ops.refund_payment(session, payment_id, amount))


@router.get("/coupons")
def get_coupons(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_coupons(session))


@router.post("/coupons")
def post_coupon(body: CouponIn, session: SessionDep, _: AdminUser):
    return ok(misc_ops.create_coupon(session, body))


@router.get("/returns")
def get_returns(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_returns(session))


@router.patch("/returns/{return_id}")
def patch_return(return_id: int, body: ReturnAdminIn, session: SessionDep, _: AdminUser):
    return ok(misc_ops.patch_return(session, return_id, body))


@router.get("/chats")
def get_chats(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_chats(session))


@router.get("/chats/{conversation_id}/messages")
def get_chat_messages(conversation_id: int, session: SessionDep, _: AdminUser):
    return ok(misc_ops.chat_messages(session, conversation_id))


@router.post("/chats/{conversation_id}/messages")
def post_chat_message(conversation_id: int, body: MessageIn, session: SessionDep, admin: AdminUser):
    return ok(misc_ops.send_chat(session, conversation_id, admin, body))


@router.post("/chats/{conversation_id}/takeover")
def post_takeover(conversation_id: int, session: SessionDep, admin: AdminUser):
    return ok(misc_ops.takeover(session, conversation_id, admin))


@router.get("/tickets")
def get_tickets(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_tickets(session))


@router.get("/shops")
def get_shops(session: SessionDep, _: AdminUser):
    return ok(shop_ops.list_shops(session))


@router.post("/shops")
def post_shop(body: ShopCreateIn, session: SessionDep, _: AdminUser):
    return ok(shop_ops.create_shop(session, body))


@router.post("/shops/{retailer_user_id}/approve")
def approve_shop(
    retailer_user_id: int,
    session: SessionDep,
    _: AdminUser,
    payload: Optional[dict] = Body(default=None),
):
    return ok(shop_ops.approve_shop(session, retailer_user_id, payload))


@router.post("/shops/{retailer_user_id}/reject")
def reject_shop(retailer_user_id: int, session: SessionDep, _: AdminUser):
    return ok(shop_ops.reject_shop(session, retailer_user_id))


@router.patch("/shops/{retailer_user_id}")
def patch_shop(retailer_user_id: int, body: ShopPatchIn, session: SessionDep, _: AdminUser):
    return ok(shop_ops.patch_shop(session, retailer_user_id, body))


@router.get("/shops/{retailer_user_id}/ledger")
def get_ledger(retailer_user_id: int, session: SessionDep, _: AdminUser):
    return ok(credit_ops.list_ledger(session, retailer_user_id))


@router.post("/shops/{retailer_user_id}/collect")
def post_collect(retailer_user_id: int, body: CollectIn, session: SessionDep, admin: AdminUser):
    return ok(
        credit_ops.credit_payment(
            session,
            retailer_user_id,
            body.amount,
            note=body.note,
            method=body.method,
            created_by=admin.id,
        )
    )


@router.get("/purchases")
def get_purchases(session: SessionDep, _: AdminUser, supplier_user_id: Optional[int] = None):
    return ok(purchase_ops.list_purchases(session, supplier_user_id))


@router.post("/purchases")
def post_purchase(body: SupplierPurchaseIn, session: SessionDep, admin: AdminUser):
    return ok(
        purchase_ops.create_purchase(
            session,
            supplier_user_id=body.supplier_user_id,
            product_id=body.product_id,
            qty=body.qty,
            unit_cost=body.unit_cost,
            note=body.note,
            created_by=admin.id,
            mark_paid=body.mark_paid,
            pay_method=body.pay_method,
        )
    )


@router.post("/purchases/{purchase_id}/pay")
def post_pay_purchase(purchase_id: int, body: SupplierPayIn, session: SessionDep, admin: AdminUser):
    return ok(
        purchase_ops.pay_purchase(
            session,
            purchase_id,
            amount=body.amount,
            pay_method=body.pay_method,
            note=body.note,
            created_by=admin.id,
        )
    )


@router.get("/customers")
def get_customers(session: SessionDep, _: AdminUser):
    return ok(misc_ops.customers(session))


@router.get("/customers/{customer_id}/presence")
def get_customer_presence(customer_id: int, session: SessionDep, _: AdminUser):
    return ok(misc_ops.customer_presence(session, customer_id))


@router.get("/reports")
def get_reports(session: SessionDep, _: AdminUser, period: str = "weekly"):
    return ok(misc_ops.reports(session, period))


@router.get("/settings")
def get_settings(session: SessionDep, _: AdminUser):
    return ok(settings_ops.get_settings_row(session))


@router.get("/integrations/check")
def get_integrations_check(_: AdminUser):
    return ok(misc_ops.integrations_check())


@router.patch("/settings")
def patch_settings(body: SettingsUpdateIn, session: SessionDep, _: AdminUser):
    return ok(settings_ops.patch_settings(session, body))


@router.get("/custom-cakes")
def get_custom_cakes(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_custom_cakes(session))


@router.patch("/custom-cakes/{req_id}")
def patch_custom_cake(req_id: int, body: CustomCakeAdminIn, session: SessionDep, _: AdminUser):
    return ok(misc_ops.patch_custom_cake(session, req_id, body.status, body.quoted_price))


@router.get("/notifications")
def get_notifications(session: SessionDep, admin: AdminUser):
    return ok(misc_ops.list_notifications(session, admin.id))


@router.post("/notifications/read")
def read_notifications(session: SessionDep, admin: AdminUser):
    return ok(misc_ops.mark_notifications_read(session, admin.id))


@router.get("/banners")
def get_banners(session: SessionDep, _: AdminUser):
    return ok(misc_ops.list_banners(session))


@router.post("/banners")
def post_banner(body: BannerIn, session: SessionDep, _: AdminUser):
    return ok(misc_ops.create_banner(session, body))
