"""Customer commerce routes — paths match monolith /api/v1/customer/*."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.deps import CurrentUser, OptionalUser, SessionDep
from app.services import addresses as address_ops
from app.services import chats as chat_ops
from app.services import custom_cakes as cake_ops
from app.services import engagement as engage_ops
from app.services import orders as order_ops
from app.services import profile as profile_ops
from app.services import returns as return_ops
from app.services.notifications import list_notifications, mark_read
from app.schemas.commerce import (
    AddressIn,
    CartItemIn,
    CartItemUpdateIn,
    CheckoutIn,
    ConversationCreateIn,
    CouponApplyIn,
    CustomCakeIn,
    MessageIn,
    OrderRateIn,
    ReturnIn,
)
from package.common.schemas import ok
from package.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/customer", tags=["customer"])


# ----- Addresses -----
@router.get("/addresses")
def addresses(session: SessionDep, user: CurrentUser):
    return ok(address_ops.list_addresses(session, user.id))


@router.post("/addresses")
def add_address(body: AddressIn, session: SessionDep, user: CurrentUser):
    return ok(address_ops.add_address(session, user, body))


@router.delete("/addresses/{address_id}")
def delete_address(address_id: int, session: SessionDep, user: CurrentUser):
    return ok(address_ops.delete_address(session, user.id, address_id))


# ----- Cart / Checkout -----
@router.get("/cart")
def get_cart(session: SessionDep, user: CurrentUser):
    return ok(order_ops.cart_summary(session, user.id))


@router.post("/cart/items")
def add_cart(body: CartItemIn, session: SessionDep, user: CurrentUser):
    return ok(
        order_ops.add_to_cart(
            session, user.id, body.product_id, body.quantity, body.variant, body.flavor, body.is_eggless
        )
    )


@router.patch("/cart/items/{item_id}")
def patch_cart(item_id: int, body: CartItemUpdateIn, session: SessionDep, user: CurrentUser):
    return ok(order_ops.patch_cart_item(session, user.id, item_id, body.quantity, body.saved_for_later))


@router.delete("/cart/items/{item_id}")
def remove_cart(item_id: int, session: SessionDep, user: CurrentUser):
    return ok(order_ops.remove_cart_item(session, user.id, item_id))


@router.post("/cart/coupon")
def coupon(body: CouponApplyIn, session: SessionDep, user: CurrentUser):
    return ok(order_ops.apply_coupon(session, user.id, body.code))


@router.post("/checkout")
def checkout(body: CheckoutIn, session: SessionDep, user: CurrentUser):
    order = order_ops.checkout(session, user.id, body)
    return ok({"order": order, "message": "Order created. Proceed to payment."})


# ----- Orders -----
@router.get("/orders")
def orders(session: SessionDep, user: CurrentUser, tab: str = Query("active")):
    return ok(order_ops.list_orders_or_returns(session, user.id, tab))


@router.get("/orders/{order_id}")
def order_detail(order_id: int, session: SessionDep, user: CurrentUser):
    return ok(order_ops.order_detail(session, order_id, user.id))


@router.get("/orders/{order_id}/track")
def track(order_id: int, session: SessionDep, user: CurrentUser):
    return ok(order_ops.track_order(session, order_id, user.id))


@router.get("/orders/{order_id}/invoice")
def invoice(order_id: int, session: SessionDep, user: CurrentUser):
    return ok(order_ops.get_invoice(session, order_id, user.id))


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: int, session: SessionDep, user: CurrentUser, reason: str = "Changed mind"):
    return ok(order_ops.cancel_order(session, order_id, user.id, reason))


@router.post("/orders/{order_id}/rate")
def rate(order_id: int, body: OrderRateIn, session: SessionDep, user: CurrentUser):
    return ok(order_ops.rate_order(session, order_id, user.id, body.rating, body.comment))


@router.post("/orders/{order_id}/reorder")
def reorder(order_id: int, session: SessionDep, user: CurrentUser):
    return ok(order_ops.reorder(session, order_id, user.id))


@router.post("/orders/{order_id}/share-track")
def share_track(order_id: int, session: SessionDep, user: CurrentUser):
    return ok(engage_ops.create_share_link(session, user, order_id))


# ----- Custom cake / Returns -----
@router.post("/custom-cakes")
def custom_cake(body: CustomCakeIn, session: SessionDep, user: CurrentUser):
    return ok(cake_ops.create_request(session, user.id, body))


@router.get("/custom-cakes")
def my_custom_cakes(session: SessionDep, user: CurrentUser):
    return ok(cake_ops.list_requests(session, user.id))


@router.post("/returns")
def create_return(body: ReturnIn, session: SessionDep, user: CurrentUser):
    return ok(return_ops.create_return(session, user.id, body))


@router.get("/returns")
def my_returns(session: SessionDep, user: CurrentUser):
    return ok(return_ops.list_returns(session, user.id))


@router.get("/returns/{return_id}")
def return_detail(return_id: int, session: SessionDep, user: CurrentUser):
    return ok(return_ops.return_detail(session, return_id, user.id))


# ----- Human chats -----
@router.post("/chats")
def start_chat(body: ConversationCreateIn, session: SessionDep, user: CurrentUser):
    return ok(chat_ops.create_conversation(session, user.id, body))


@router.get("/chats")
def chats(session: SessionDep, user: CurrentUser):
    return ok(chat_ops.list_conversations(session, user))


@router.get("/chats/{conversation_id}/messages")
def messages(conversation_id: int, session: SessionDep, user: CurrentUser):
    return ok(chat_ops.list_messages(session, conversation_id, user))


@router.post("/chats/{conversation_id}/messages")
def send(conversation_id: int, body: MessageIn, session: SessionDep, user: CurrentUser):
    return ok(
        chat_ops.send_message(
            session,
            conversation_id,
            user.id,
            "customer",
            body.content,
            body.message_type,
            body.media_url,
            body.metadata_json,
        )
    )


# ----- Notifications / Profile -----
@router.get("/notifications")
def notifications(session: SessionDep, user: CurrentUser, unread_only: bool = False):
    return ok(list_notifications(session, user.id, unread_only))


@router.post("/notifications/read")
def read_notifications(session: SessionDep, user: CurrentUser, notification_id: int | None = None):
    return ok(mark_read(session, user.id, notification_id))


@router.get("/profile/summary")
def profile_summary(session: SessionDep, user: CurrentUser):
    return ok(profile_ops.profile_summary(session, user))


# ----- Wallet / Referral / Subscriptions / Gift / Corporate / Public track -----
@router.get("/wallet")
def wallet(session: SessionDep, user: CurrentUser):
    return ok(engage_ops.wallet_summary(session, user))


@router.post("/wallet/add")
def wallet_add(session: SessionDep, user: CurrentUser, amount: float = 200, method: str = "UPI"):
    return ok(engage_ops.wallet_add_money(session, user, amount, method))


@router.get("/referral")
def referral(session: SessionDep, user: CurrentUser):
    return ok(engage_ops.referral_summary(session, user))


@router.post("/referral/apply")
def referral_apply(session: SessionDep, user: CurrentUser, code: str):
    return ok(engage_ops.apply_referral(session, user, code))


@router.get("/subscriptions")
def subscriptions(session: SessionDep, user: CurrentUser):
    return ok(engage_ops.list_subscriptions(session, user))


@router.post("/subscriptions/{plan_id}")
def subscribe(plan_id: int, session: SessionDep, user: CurrentUser):
    return ok(engage_ops.subscribe(session, user, plan_id))


@router.get("/gift-hampers")
def gift_hampers(session: SessionDep):
    return ok(engage_ops.gift_hampers(session))


@router.post("/corporate")
def corporate_inquiry(body: dict[str, Any], session: SessionDep, user: OptionalUser):
    return ok(engage_ops.create_corporate(session, user, body))


@router.get("/track/share/{token}")
def public_share_track(token: str, session: SessionDep):
    return ok(engage_ops.public_track(session, token))
