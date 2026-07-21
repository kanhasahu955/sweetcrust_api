from __future__ import annotations
from fastapi import APIRouter
from app.controllers import support as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.commerce import ConversationCreateIn, MessageIn
from package.common.schemas import ok

from app.controllers.support_async import SupportController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await SupportController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/customer", tags=["support"])

@router.post("/chats")
async def post_chats(body: ConversationCreateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.create_chat, user.id, body))

@router.get("/chats")
async def get_chats(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.list_chats, user))

@router.get("/chats/{conversation_id}/messages")
async def get_conversation_id_messages(conversation_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.list_messages, conversation_id, user))

@router.post("/chats/{conversation_id}/messages")
async def post_conversation_id_messages(conversation_id: int, body: MessageIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.send, conversation_id, user.id, body))
