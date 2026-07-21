"""Customer commerce routes — paths match monolith /api/v1/customer/*."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Query
from app.deps import CurrentUser, OptionalUser, AsyncSessionDep
from app.services import addresses as address_ops
from app.services import chats as chat_ops
from app.services import custom_cakes as cake_ops
from app.services import engagement as engage_ops
from app.services import orders as order_ops
from app.services import profile as profile_ops
from app.services import returns as return_ops
from app.services.notifications import list_notifications, mark_read
from app.schemas.commerce import AddressIn, CartItemIn, CartItemUpdateIn, CheckoutIn, ConversationCreateIn, CouponApplyIn, CustomCakeIn, MessageIn, OrderRateIn, ReturnIn
from package.common.schemas import ok
from package.logger import get_logger
from app.controllers.commerce_async import CommerceController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await CommerceController(session).call(fn, *args, **kwargs)

logger = get_logger(__name__)
router = APIRouter(prefix='/customer', tags=['customer'])

@router.get('/addresses')
async def addresses(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, address_ops.list_addresses, user.id))

@router.post('/addresses')
async def add_address(body: AddressIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, address_ops.add_address, user, body))

@router.delete('/addresses/{address_id}')
async def delete_address(address_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, address_ops.delete_address, user.id, address_id))

@router.get('/cart')
async def get_cart(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.cart_summary, user.id))

@router.post('/cart/items')
async def add_cart(body: CartItemIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.add_to_cart, user.id, body.product_id, body.quantity, body.variant, body.flavor, body.is_eggless))

@router.patch('/cart/items/{item_id}')
async def patch_cart(item_id: int, body: CartItemUpdateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.patch_cart_item, user.id, item_id, body.quantity, body.saved_for_later))

@router.delete('/cart/items/{item_id}')
async def remove_cart(item_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.remove_cart_item, user.id, item_id))

@router.post('/cart/coupon')
async def coupon(body: CouponApplyIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.apply_coupon, user.id, body.code))

@router.post('/checkout')
async def checkout(body: CheckoutIn, session: AsyncSessionDep, user: CurrentUser):
    order = await _domain(session, order_ops.checkout, user.id, body)
    return ok({'order': order, 'message': 'Order created. Proceed to payment.'})

@router.get('/orders')
async def orders(session: AsyncSessionDep, user: CurrentUser, tab: str=Query('active')):
    return ok(await _domain(session, order_ops.list_orders_or_returns, user.id, tab))

@router.get('/orders/{order_id}')
async def order_detail(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.order_detail, order_id, user.id))

@router.get('/orders/{order_id}/track')
async def track(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.track_order, order_id, user.id))

@router.get('/orders/{order_id}/invoice')
async def invoice(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.get_invoice, order_id, user.id))

@router.post('/orders/{order_id}/cancel')
async def cancel(order_id: int, session: AsyncSessionDep, user: CurrentUser, reason: str='Changed mind'):
    return ok(await _domain(session, order_ops.cancel_order, order_id, user.id, reason))

@router.post('/orders/{order_id}/rate')
async def rate(order_id: int, body: OrderRateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.rate_order, order_id, user.id, body.rating, body.comment))

@router.post('/orders/{order_id}/reorder')
async def reorder(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, order_ops.reorder, order_id, user.id))

@router.post('/orders/{order_id}/share-track')
async def share_track(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, engage_ops.create_share_link, user, order_id))

@router.post('/custom-cakes')
async def custom_cake(body: CustomCakeIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, cake_ops.create_request, user.id, body))

@router.get('/custom-cakes')
async def my_custom_cakes(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, cake_ops.list_requests, user.id))

@router.post('/returns')
async def create_return(body: ReturnIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, return_ops.create_return, user.id, body))

@router.get('/returns')
async def my_returns(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, return_ops.list_returns, user.id))

@router.get('/returns/{return_id}')
async def return_detail(return_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, return_ops.return_detail, return_id, user.id))

@router.post('/chats')
async def start_chat(body: ConversationCreateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, chat_ops.create_conversation, user.id, body))

@router.get('/chats')
async def chats(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, chat_ops.list_conversations, user))

@router.get('/chats/{conversation_id}/messages')
async def messages(conversation_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, chat_ops.list_messages, conversation_id, user))

@router.post('/chats/{conversation_id}/messages')
async def send(conversation_id: int, body: MessageIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, chat_ops.send_message, conversation_id, user.id, 'customer', body.content, body.message_type, body.media_url, body.metadata_json))

@router.get('/notifications')
async def notifications(session: AsyncSessionDep, user: CurrentUser, unread_only: bool=False):
    return ok(await _domain(session, list_notifications, user.id, unread_only))

@router.post('/notifications/read')
async def read_notifications(session: AsyncSessionDep, user: CurrentUser, notification_id: int | None=None):
    return ok(await _domain(session, mark_read, user.id, notification_id))

@router.get('/profile/summary')
async def profile_summary(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, profile_ops.profile_summary, user))

@router.get('/wallet')
async def wallet(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, engage_ops.wallet_summary, user))

@router.post('/wallet/add')
async def wallet_add(session: AsyncSessionDep, user: CurrentUser, amount: float=200, method: str='UPI'):
    return ok(await _domain(session, engage_ops.wallet_add_money, user, amount, method))

@router.get('/referral')
async def referral(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, engage_ops.referral_summary, user))

@router.post('/referral/apply')
async def referral_apply(session: AsyncSessionDep, user: CurrentUser, code: str):
    return ok(await _domain(session, engage_ops.apply_referral, user, code))

@router.get('/subscriptions')
async def subscriptions(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, engage_ops.list_subscriptions, user))

@router.post('/subscriptions/{plan_id}')
async def subscribe(plan_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, engage_ops.subscribe, user, plan_id))

@router.get('/gift-hampers')
async def gift_hampers(session: AsyncSessionDep):
    return ok(await _domain(session, engage_ops.gift_hampers))

@router.post('/corporate')
async def corporate_inquiry(body: dict[str, Any], session: AsyncSessionDep, user: OptionalUser):
    return ok(await _domain(session, engage_ops.create_corporate, user, body))

@router.get('/track/share/{token}')
async def public_share_track(token: str, session: AsyncSessionDep):
    return ok(await _domain(session, engage_ops.public_track, token))
