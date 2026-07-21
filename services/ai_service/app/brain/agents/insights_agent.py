"""Owner dashboard insights — DB facts only; optional LLM polish."""
from __future__ import annotations

import json
from package.logger import get_logger
import time

from langchain_core.messages import HumanMessage, SystemMessage
from sqlmodel import Session, func, select

from app.brain.llm import get_chat_model
from app.brain.prompts import INSIGHTS_SYSTEM
from app.models.catalog import Product
from app.models.commerce import Order
from app.models.enums import OrderStatus, StockStatus
from app.config import get_settings

logger = get_logger(__name__)

# ponytail: in-process TTL cache; upgrade to Redis if multi-worker needs shared insights
_LLM_CACHE: tuple[float, list[str]] | None = None
_LLM_TTL_SEC = 300


class InsightsAgent:
    def business_insights(self, session: Session, *, use_llm: bool = False) -> list[str]:
        facts = self._facts(session)
        if not use_llm:
            return facts

        global _LLM_CACHE
        now = time.monotonic()
        if _LLM_CACHE and now - _LLM_CACHE[0] < _LLM_TTL_SEC:
            return _LLM_CACHE[1]

        settings = get_settings()
        if not settings.llm_configured or (settings.ai_dev_mock_llm and settings.is_dev):
            return facts

        try:
            model = get_chat_model(temperature=0.3, max_tokens=400)
            msg = model.invoke(
                [
                    SystemMessage(content=INSIGHTS_SYSTEM),
                    HumanMessage(content="Facts:\n" + "\n".join(f"- {f}" for f in facts)),
                ]
            )
            text = getattr(msg, "content", "") or ""
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(text[start : end + 1])
                out = [str(x) for x in (data.get("insights") or []) if x]
                if out:
                    _LLM_CACHE = (now, out[:6])
                    return out[:6]
        except Exception:
            logger.exception("insights LLM failed; using facts")
        return facts

    @staticmethod
    def _facts(session: Session) -> list[str]:
        facts: list[str] = []
        low = session.exec(
            select(Product).where(Product.stock_status == StockStatus.LOW_STOCK).limit(3)
        ).all()
        for p in low:
            facts.append(f"“{p.name}” is low stock ({p.stock_qty} left) — restock suggested.")

        out = session.exec(
            select(Product).where(Product.stock_status == StockStatus.OUT_OF_STOCK).limit(3)
        ).all()
        for p in out:
            facts.append(f"“{p.name}” is out of stock.")

        top = session.exec(select(Product).order_by(Product.sales_count.desc()).limit(1)).first()
        if top and (top.sales_count or 0) > 0:
            facts.append(f"Top seller: {top.name} ({top.sales_count} sold).")

        active = session.exec(
            select(func.count()).select_from(Product).where(Product.is_active == True)  # noqa: E712
        ).one()
        facts.append(f"Active catalog products: {int(active or 0)}.")

        open_orders = session.exec(
            select(func.count())
            .select_from(Order)
            .where(~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]))
        ).one()
        facts.append(f"Open orders in progress: {int(open_orders or 0)}.")

        if not facts:
            facts.append("Not enough catalog/order data yet for insights.")
        return facts[:6]


_agent = InsightsAgent()
business_insights = _agent.business_insights
