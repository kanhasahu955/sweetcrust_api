from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query
from app.controllers import search as ctrl
from app.deps import AsyncSessionDep, OptionalUser
from package.common.schemas import ok

from app.controllers.search_async import SearchController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await SearchController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["search"])

@router.get("/customer/search")
async def get_customer_search(session: AsyncSessionDep, user: OptionalUser = None, q: Optional[str] = None,
           category_id: Optional[int] = None, page: int = Query(1, ge=1),
           page_size: int = Query(20, ge=1, le=100),
           min_price: Optional[float] = None, max_price: Optional[float] = None):
    return ok(await _domain(session, ctrl.search, q, category_id, page, page_size, min_price, max_price))

@router.get("/customer/search/suggest")
async def get_search_suggest(session: AsyncSessionDep, q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)):
    return ok(await _domain(session, ctrl.suggest, q, limit))

@router.get("/customer/products")
async def get_customer_products(session: AsyncSessionDep, user: OptionalUser = None, q: Optional[str] = None,
                    category_id: Optional[int] = None, page: int = Query(1, ge=1),
                    page_size: int = Query(20, ge=1, le=100)):
    return ok(await _domain(session, ctrl.search, q, category_id, page, page_size))
