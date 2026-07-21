"""SweetCrust AI assistant — LangGraph agentic RAG + rules fallback."""

from __future__ import annotations

from package.logger import get_logger
import re
from typing import Any, Optional

from sqlmodel import Session, select

from app.brain.guardrails import filter_ai_reply, filter_user_message
from app.brain.monitor import configure_tracing, finish_run, start_run
from app.config import get_settings
from app.models.catalog import Product
from app.models.commerce import Order
from app.models.enums import UserRole
from app.models.user import User

logger = get_logger(__name__)


class ChatbotAgent:
    def respond(
        self,
        session: Session,
        user_id: int,
        message: str,
        language: str = "en",
        *,
        audience: Optional[str] = None,
        history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        configure_tracing()

        if audience not in ("retailer", "customer"):
            user = session.get(User, user_id)
            audience = "retailer" if user and user.role == UserRole.RETAILER else "customer"

        gate = filter_user_message(message)
        if not gate.get("allowed"):
            return {
                "reply": gate.get("reply") or "I can only help with SweetCrust Bakery app topics.",
                "language": language,
                "products": [],
                "actions": [{"type": "handover_human"}],
                "quick_replies": [
                    "Eggless chocolate cakes",
                    "Where is my order?",
                    "Talk to bakery owner",
                ],
                "provider": "guardrails",
                "blocked": True,
                "reason": gate.get("reason"),
                "agentic": False,
            }

        message = gate.get("text") or message

        if settings.llm_configured and not (settings.ai_dev_mock_llm and not settings.llm_api_key):
            try:
                from app.brain.graphs.chatbot_graph import run_chatbot_graph

                return run_chatbot_graph(
                    session,
                    user_id,
                    message,
                    language,
                    audience=audience,
                    history=history,
                )
            except Exception:
                logger.exception("LangGraph chatbot failed — using rules")

        run_id = start_run(user_id=user_id, audience=audience or "customer", message=message, provider="rules")
        result = self._respond_rules(session, user_id, message, language, audience=audience or "customer")
        result["reply"] = filter_ai_reply(result.get("reply") or "")
        result["agentic"] = False
        finish_run(run_id, reply=result.get("reply") or "", provider="rules")
        return result

    def _respond_rules(
        self,
        session: Session,
        user_id: int,
        message: str,
        language: str,
        *,
        audience: str = "customer",
    ) -> dict[str, Any]:
        text = message.lower().strip()
        products: list[Product] = []
        actions: list[dict[str, Any]] = []
        reply = ""

        if audience == "retailer" and any(k in text for k in ("credit", "udhaar", "balance", "limit")):
            from app.brain.rag.pipeline import hybrid_retrieve
            from app.models.user import RetailerProfile

            profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user_id)).first()
            if profile:
                left = max(0.0, float(profile.credit_limit) - float(profile.outstanding_balance))
                reply = (
                    f"Your shop credit limit is ₹{profile.credit_limit:.0f}. "
                    f"Outstanding udhaar ₹{profile.outstanding_balance:.0f}. Available ₹{left:.0f}."
                )
            else:
                rag = hybrid_retrieve(session, message)
                reply = (rag.get("context") or "Ask the bakery owner to set your credit limit.")[:500]
        elif any(k in text for k in ("order", "where is my", "track", "मेरा ऑर्डर")):
            order = session.exec(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())).first()
            if order:
                reply = f"Your latest order {order.order_number} is currently *{order.status.value.replace('_', ' ')}*."
                actions.append({"type": "open_tracking", "order_id": order.id})
            else:
                reply = "I couldn't find an active order. Would you like help browsing cakes?"
        elif "eggless" in text or "एगलेस" in text:
            products = list(session.exec(select(Product).where(Product.is_eggless == True, Product.is_active == True).limit(5)).all())  # noqa: E712
            reply = "Here are popular eggless options from SweetCrust:"
            actions.append({"type": "show_products"})
        elif "sugar" in text or "sugar-free" in text or "डायबिटिक" in text:
            products = list(session.exec(select(Product).where(Product.is_sugar_free == True, Product.is_active == True).limit(5)).all())  # noqa: E712
            reply = "Sugar-free picks that still taste indulgent:"
        elif "under" in text or "₹" in text or "rs" in text or "budget" in text:
            budget = self._extract_budget(text) or 1000
            products = list(
                session.exec(
                    select(Product)
                    .where(Product.selling_price <= budget, Product.is_active == True)  # noqa: E712
                    .order_by(Product.rating.desc())
                    .limit(5)
                ).all()
            )
            reply = f"Birthday / celebration cakes under ₹{budget:.0f}:"
            actions.append({"type": "show_products"})
        elif any(k in text for k in ("return", "damaged", "refund", "खराब")):
            reply = (
                "Yes — if an item arrives damaged, you can request a replacement or refund within 24 hours "
                "with photos. I can open the return flow or connect you to the bakery owner."
            )
            actions.append({"type": "open_return"})
            actions.append({"type": "handover_human"})
        elif any(k in text for k in ("custom", "customise", "customize", "design")):
            reply = "I can help start a custom cake request — occasion, flavour, weight, and a reference photo."
            actions.append({"type": "start_custom_cake"})
        elif any(k in text for k in ("human", "agent", "owner", "talk to", "बात", "call")):
            reply = "I'll connect you to the SweetCrust bakery owner now."
            actions.append({"type": "handover_human"})
        else:
            from app.brain.rag.pipeline import hybrid_retrieve

            rag = hybrid_retrieve(session, message)
            if rag.get("context"):
                reply = "From SweetCrust knowledge:\n" + rag["context"].split("\n\n")[0][:600]
            else:
                products = list(session.exec(select(Product).where(Product.is_bestseller == True).limit(4)).all())  # noqa: E712
                reply = (
                    "I'm your SweetCrust assistant — ask about products, shop orders, credit, delivery, "
                    "or say talk to owner. Here are popular items:"
                )
                actions.append({"type": "show_products"})

        return {
            "reply": reply,
            "language": language,
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "selling_price": p.selling_price,
                    "cover_image_url": p.cover_image_url,
                    "is_eggless": p.is_eggless,
                }
                for p in products
            ],
            "actions": actions,
            "quick_replies": (
                [
                    "What is my credit balance?",
                    "Where is my shop order?",
                    "Talk to bakery owner",
                ]
                if audience == "retailer"
                else [
                    "Eggless chocolate cakes",
                    "Birthday cake under ₹1000",
                    "Where is my order?",
                    "Talk to bakery owner",
                ]
            ),
            "provider": "rules+rag",
            "rag_used": True,
        }

    @staticmethod
    def _extract_budget(text: str) -> float | None:
        m = re.search(r"₹\s?(\d+)", text)
        if m:
            return float(m.group(1))
        m = re.search(r"under\s+(\d+)", text)
        if m:
            return float(m.group(1))
        m = re.search(r"(\d+)\s*(rs|rupees)", text)
        if m:
            return float(m.group(1))
        return None


_agent = ChatbotAgent()
respond = _agent.respond
