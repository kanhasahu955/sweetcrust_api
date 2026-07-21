from __future__ import annotations
from fastapi import APIRouter
from app.controllers import invoices as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from package.common.schemas import ok

from app.controllers.invoice_async import InvoiceController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await InvoiceController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/customer", tags=["invoice"])

@router.get("/orders/{order_id}/invoice")
async def get_order_id_invoice(order_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.get_invoice, order_id, user.id))
