"""Temporary retailer BFF (non-AI) until commerce owns B2B."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import RetailerUser, SessionDep
from app.services import retailer_bff as r_ops
from app.schemas.admin import (
    BulkOrderIn,
    CallbackIn,
    MessageIn,
    ProductRequestIn,
    RetailerProfilePatchIn,
)
from package.common.schemas import APIModel, ok
from package.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/retailer", tags=["retailer"])


class PresenceIn(APIModel):
    online: bool = True


@router.get("/me")
def get_me(session: SessionDep, user: RetailerUser):
    return ok(r_ops.me(session, user))


@router.patch("/me")
def patch_me(body: RetailerProfilePatchIn, session: SessionDep, user: RetailerUser):
    return ok(r_ops.patch_me(session, user, body))


@router.post("/me/submit")
def submit(session: SessionDep, user: RetailerUser):
    return ok(r_ops.submit(session, user))


@router.post("/presence")
def presence(body: PresenceIn, session: SessionDep, user: RetailerUser):
    return ok(r_ops.presence(session, user, body.online))


@router.get("/catalog")
def catalog(session: SessionDep, _: RetailerUser):
    return ok(r_ops.catalog(session))


@router.post("/products/request")
def product_request(body: ProductRequestIn, session: SessionDep, user: RetailerUser):
    return ok(
        r_ops.request_product(
            session,
            user,
            {
                "image_urls": body.image_urls,
                "cover_image": body.cover_image,
                "suggestions": body.suggestions,
                "notes": body.notes,
            },
        )
    )


@router.post("/orders")
def create_order(body: BulkOrderIn, session: SessionDep, user: RetailerUser):
    return ok(
        r_ops.create_bulk_order(
            session,
            user,
            [line.model_dump() for line in body.lines],
            body.note,
            pay_mode=body.pay_mode,
        )
    )


@router.get("/orders")
def orders(session: SessionDep, user: RetailerUser):
    return ok(r_ops.my_orders(session, user))


@router.get("/orders/{order_id}")
def order_detail(order_id: int, session: SessionDep, user: RetailerUser):
    return ok(r_ops.get_order(session, user, order_id))


@router.get("/chats")
def chats(session: SessionDep, user: RetailerUser):
    return ok(r_ops.list_chats(session, user))


@router.post("/chats/support")
def open_support(session: SessionDep, user: RetailerUser, ai: bool = False):
    return ok(r_ops.open_support(session, user, ai=ai))


@router.get("/chats/{conversation_id}/messages")
def messages(conversation_id: int, session: SessionDep, user: RetailerUser):
    return ok(r_ops.list_messages(session, conversation_id, user))


@router.post("/chats/{conversation_id}/messages")
def send(conversation_id: int, body: MessageIn, session: SessionDep, user: RetailerUser):
    return ok(
        r_ops.send_message(
            session,
            conversation_id,
            user,
            body.content,
            body.message_type,
            body.media_url,
            body.metadata_json,
        )
    )


@router.post("/calls/callback")
def request_callback(body: CallbackIn, session: SessionDep, user: RetailerUser):
    return ok(r_ops.request_callback(session, user, body.note))
