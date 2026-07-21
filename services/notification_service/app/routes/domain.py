from __future__ import annotations
from fastapi import APIRouter
from app.controllers import notifications as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from package.common.schemas import ok

from app.controllers.notification_async import NotificationController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await NotificationController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/customer", tags=["notifications"])

@router.get("/notifications")
async def get_notifications(session: AsyncSessionDep, user: CurrentUser, unread_only: bool = False):
    return ok(await _domain(session, ctrl.list_all, user.id, unread_only))

@router.post("/notifications/read")
async def post_notifications_read(session: AsyncSessionDep, user: CurrentUser, notification_id: int | None = None):
    return ok(await _domain(session, ctrl.mark, user.id, notification_id))
