"""User profile routes — async OOP."""
from __future__ import annotations
from fastapi import APIRouter
from app.controllers import auth as ctrl
from app.controllers.user_async import UserController
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.auth import ProfileUpdateIn

router = APIRouter(prefix="/auth", tags=["user"])


async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await UserController(session).call(fn, *args, **kwargs)


@router.get("/me")
async def me(user: CurrentUser):
    return ctrl.me(user)


@router.patch("/me")
async def update_me(body: ProfileUpdateIn, user: CurrentUser, session: AsyncSessionDep):
    return await _domain(session, ctrl.update_me, user, body.model_dump(exclude_unset=True))
