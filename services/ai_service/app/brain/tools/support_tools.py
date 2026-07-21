"""LangChain tools for SweetCrust support agent (agentic RAG + shop/customer ops)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.brain.rag.pipeline import hybrid_retrieve
from app.models.catalog import Product
from app.models.commerce import Order
from app.models.user import RetailerProfile, User


class RagIn(BaseModel):
    query: str = Field(description="What to look up in bakery policies / FAQs")


class OrderIn(BaseModel):
    order_number: Optional[str] = Field(default=None, description="Optional order number like SC-…")


class ProductIn(BaseModel):
    q: Optional[str] = Field(default=None, description="Name keyword")
    eggless: Optional[bool] = None
    sugar_free: Optional[bool] = None
    max_price: Optional[float] = None
    bestseller: Optional[bool] = None


def build_support_tools(
    session: Session,
    user_id: int,
    *,
    audience: str = "customer",
    on_rag: Optional[Callable[[int], None]] = None,
) -> list[StructuredTool]:
    tool_log: list[str] = []

    def _track(name: str) -> None:
        tool_log.append(name)

    def agentic_rag(query: str) -> str:
        """Agentic RAG over bakery policies and admin FAQs. Call for policy, credit, delivery, GST, hours."""
        _track("agentic_rag")
        result = hybrid_retrieve(session, query)
        if on_rag:
            on_rag(result.get("chunk_count") or 0)
        if not result.get("context"):
            return "No matching policy/FAQ found."
        return result["context"]

    def latest_order_status(order_number: Optional[str] = None) -> str:
        """Look up this user's latest order status (or a specific order number)."""
        _track("latest_order_status")
        stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        if order_number:
            order = session.exec(select(Order).where(Order.order_number == order_number, Order.user_id == user_id)).first()
        else:
            order = session.exec(stmt).first()
        if not order:
            return "No orders found for this account."
        return (
            f"Order {order.order_number}: status={order.status.value}, "
            f"amount=₹{order.final_amount:.0f}, pay={getattr(order, 'payment_status', None)}"
        )

    def search_products(
        q: Optional[str] = None,
        eggless: Optional[bool] = None,
        sugar_free: Optional[bool] = None,
        max_price: Optional[float] = None,
        bestseller: Optional[bool] = None,
    ) -> str:
        """Search catalog products for recommendations."""
        _track("search_products")
        stmt = select(Product).where(Product.is_active == True, Product.is_draft == False)  # noqa: E712
        if eggless is True:
            stmt = stmt.where(Product.is_eggless == True)  # noqa: E712
        if sugar_free is True:
            stmt = stmt.where(Product.is_sugar_free == True)  # noqa: E712
        if bestseller is True:
            stmt = stmt.where(Product.is_bestseller == True)  # noqa: E712
        if max_price is not None:
            stmt = stmt.where(Product.selling_price <= max_price)
        if q:
            from sqlalchemy import func as sa_func

            like = f"%{q.lower()}%"
            stmt = stmt.where(sa_func.lower(Product.name).like(like))
        rows = list(session.exec(stmt.order_by(Product.rating.desc()).limit(5)).all())
        if not rows:
            return "No matching products."
        lines = []
        for p in rows:
            price = getattr(p, "shop_price", None) or p.selling_price
            label = "shop" if audience == "retailer" else "sell"
            lines.append(f"{p.id}|{p.name}|{label}=₹{price:.0f}|eggless={p.is_eggless}")
        return "\n".join(lines)

    def shop_credit() -> str:
        """Retailer-only: credit limit, outstanding (udhaar), approval status."""
        _track("shop_credit")
        if audience != "retailer":
            return "Credit/udhaar is for village shops only."
        profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user_id)).first()
        if not profile:
            return "Shop profile not found."
        left = max(0.0, float(profile.credit_limit) - float(profile.outstanding_balance))
        return (
            f"approval={profile.approval_status}; credit_allowed={profile.credit_allowed}; "
            f"limit=₹{profile.credit_limit:.0f}; outstanding=₹{profile.outstanding_balance:.0f}; "
            f"available=₹{left:.0f}; blocked={profile.is_blocked}"
        )

    def handover_to_owner(reason: str = "customer requested human") -> str:
        """Escalate to bakery owner / human support."""
        _track("handover_to_owner")
        return f"HANDOVER:{reason}"

    tools = [
        StructuredTool.from_function(
            func=agentic_rag,
            name="agentic_rag",
            description=agentic_rag.__doc__ or "RAG search",
            args_schema=RagIn,
        ),
        StructuredTool.from_function(
            func=latest_order_status,
            name="latest_order_status",
            description=latest_order_status.__doc__ or "Order status",
            args_schema=OrderIn,
        ),
        StructuredTool.from_function(
            func=search_products,
            name="search_products",
            description=search_products.__doc__ or "Product search",
            args_schema=ProductIn,
        ),
        StructuredTool.from_function(
            func=handover_to_owner,
            name="handover_to_owner",
            description=handover_to_owner.__doc__ or "Handover",
        ),
    ]
    if audience == "retailer":
        tools.insert(
            1,
            StructuredTool.from_function(
                func=shop_credit,
                name="shop_credit",
                description=shop_credit.__doc__ or "Shop credit",
            ),
        )

    # Attach log for caller
    for t in tools:
        setattr(t, "_sweetcrust_tool_log", tool_log)
    return tools


def tool_names_used(tools: list[StructuredTool]) -> list[str]:
    if not tools:
        return []
    log = getattr(tools[0], "_sweetcrust_tool_log", None)
    return list(log or [])
