"""LangGraph agentic chatbot: guardrails → ReAct tools (RAG/orders/products) → parse."""

from __future__ import annotations

from package.logger import get_logger
import re
from typing import Any, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from sqlmodel import Session, select

from app.brain.guardrails import filter_ai_reply, filter_user_message
from app.brain.llm import chat_completion, get_chat_model
from app.brain.monitor import configure_tracing, finish_run, note_tools, start_run
from app.brain.parser.chatbot import parse_chatbot_output
from app.brain.prompts.chatbot import agentic_system_prompt, chatbot_prompt
from app.brain.prompts.guardrails import GUARDRAILS_SYSTEM_ADDON
from app.brain.rag.pipeline import ensure_retailer_docs_seeded, hybrid_retrieve
from app.brain.rag.retriever import retrieve_context
from app.brain.tools.support_tools import build_support_tools, tool_names_used
from app.config import get_settings
from app.models.catalog import Product
from app.models.commerce import Order
from app.models.enums import UserRole
from app.models.user import RetailerProfile, User

logger = get_logger(__name__)


class ChatState(TypedDict, total=False):
    message: str
    language: str
    user_id: int
    audience: str
    user_context: str
    rag_context: str
    blocked: bool
    block_reply: str
    block_reason: str
    raw_llm: str
    parsed: dict
    products: list
    reply: str
    actions: list
    provider: str
    model: str
    history: list


def _build_user_context(session: Session, user_id: int, audience: str) -> str:
    user = session.get(User, user_id)
    order = session.exec(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())).first()
    bestsellers = list(
        session.exec(select(Product).where(Product.is_bestseller == True, Product.is_active == True).limit(5)).all()  # noqa: E712
    )
    lines = [
        "Bakery: SweetCrust. GST invoices, UPI, credit for approved shops, same-day delivery when stocked.",
        f"Audience: {audience}",
        f"User: {(user.name if user else None) or (user.phone if user else user_id)}",
    ]
    if audience == "retailer":
        profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user_id)).first()
        if profile:
            left = max(0.0, float(profile.credit_limit) - float(profile.outstanding_balance))
            lines.append(
                f"Shop={profile.shop_name}; approval={profile.approval_status}; "
                f"credit_limit=₹{profile.credit_limit:.0f}; outstanding=₹{profile.outstanding_balance:.0f}; "
                f"available=₹{left:.0f}"
            )
    if order:
        lines.append(
            f"Latest order: {order.order_number} status={order.status.value} amount=₹{order.final_amount:.0f}"
        )
    else:
        lines.append("No recent orders.")
    if bestsellers:
        lines.append("Bestsellers: " + "; ".join(f"{p.name} ₹{p.selling_price:.0f}" for p in bestsellers))
    return "\n".join(lines)


def _detect_audience(session: Session, user_id: int, audience: Optional[str]) -> str:
    if audience in ("retailer", "customer"):
        return audience
    user = session.get(User, user_id)
    if user and user.role == UserRole.RETAILER:
        return "retailer"
    return "customer"


def node_guardrails(state: ChatState) -> ChatState:
    gate = filter_user_message(state["message"])
    if not gate.get("allowed"):
        return {
            **state,
            "blocked": True,
            "block_reply": gate.get("reply") or "I can only help with SweetCrust Bakery app topics.",
            "block_reason": gate.get("reason") or "off_topic",
            "message": gate.get("text") or state["message"],
        }
    return {
        **state,
        "blocked": False,
        "message": gate.get("text") or state["message"],
    }


def node_rag(state: ChatState) -> ChatState:
    """Legacy linear RAG node (fallback graph)."""
    if state.get("blocked"):
        return state
    ctx = retrieve_context(state["message"])
    return {**state, "rag_context": ctx or "No extra policy snippets."}


def node_llm(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return state
    settings = get_settings()
    try:
        messages = chatbot_prompt.format_messages(
            guardrails=GUARDRAILS_SYSTEM_ADDON,
            rag_context=state.get("rag_context") or "",
            user_context=state.get("user_context") or "",
            language=state.get("language") or "en",
            message=state["message"],
        )
        model = get_chat_model()
        if settings.llm_provider.lower() in ("openai", "groq"):
            try:
                model = model.bind(response_format={"type": "json_object"})
            except Exception:
                pass
        result = model.invoke(messages)
        raw = result.content if isinstance(result.content, str) else str(result.content)
        return {
            **state,
            "raw_llm": raw,
            "provider": f"langchain:{settings.llm_provider}",
            "model": settings.llm_model,
        }
    except Exception:
        logger.exception("LangGraph LLM node failed — fallback completion")
        raw = chat_completion(
            [
                {
                    "role": "system",
                    "content": f"{GUARDRAILS_SYSTEM_ADDON}\nContext:\n{state.get('user_context')}\nRAG:\n{state.get('rag_context')}",
                },
                {"role": "user", "content": state["message"]},
            ],
            json_mode=True,
        )
        return {**state, "raw_llm": raw, "provider": settings.llm_provider, "model": settings.llm_model}


def node_parse(state: ChatState) -> ChatState:
    if state.get("blocked"):
        return {
            **state,
            "reply": filter_ai_reply(state.get("block_reply") or ""),
            "actions": [{"type": "handover_human"}],
            "parsed": {},
            "products": [],
            "provider": "guardrails",
        }
    parsed = parse_chatbot_output(state.get("raw_llm") or "")
    reply = filter_ai_reply(parsed.get("reply") or state.get("raw_llm") or "")
    actions = parsed.get("actions") or []
    return {**state, "parsed": parsed, "reply": reply, "actions": actions}


def _route_after_guardrails(state: ChatState) -> str:
    return "blocked_end" if state.get("blocked") else "rag"


def build_chatbot_graph():
    """Linear LangGraph (guardrails → RAG → LLM → parse) — used as fallback."""
    g = StateGraph(ChatState)
    g.add_node("guardrails", node_guardrails)
    g.add_node("rag", node_rag)
    g.add_node("llm", node_llm)
    g.add_node("parse", node_parse)
    g.add_edge(START, "guardrails")
    g.add_conditional_edges(
        "guardrails",
        _route_after_guardrails,
        {"rag": "rag", "blocked_end": "parse"},
    )
    g.add_edge("rag", "llm")
    g.add_edge("llm", "parse")
    g.add_edge("parse", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_chatbot_graph()
    return _GRAPH


def _history_messages(history: Optional[list[dict[str, str]]]) -> list:
    msgs = []
    for h in history or []:
        role = (h.get("role") or "user").lower()
        content = h.get("content") or ""
        if not content:
            continue
        if role in ("assistant", "ai"):
            msgs.append(AIMessage(content=content))
        elif role == "system":
            msgs.append(SystemMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs[-8:]  # keep short for cost


def _extract_tool_names_from_messages(messages: list) -> list[str]:
    names: list[str] = []
    for m in messages:
        for call in getattr(m, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                names.append(str(name))
    return names


def _products_from_tool_text(session: Session, text: str) -> list[Product]:
    ids = [int(x) for x in re.findall(r"(?:^|\n)(\d+)\|", text or "")]
    if not ids:
        return []
    out = []
    for pid in ids[:5]:
        p = session.get(Product, pid)
        if p:
            out.append(p)
    return out


def run_agentic_chatbot(
    session: Session,
    user_id: int,
    message: str,
    language: str = "en",
    *,
    audience: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """Primary path: LangGraph ReAct agent + tools (agentic RAG)."""
    settings = get_settings()
    configure_tracing()
    ensure_retailer_docs_seeded()
    audience = _detect_audience(session, user_id, audience)
    user_context = _build_user_context(session, user_id, audience)

    gate = filter_user_message(message)
    if not gate.get("allowed"):
        return {
            "reply": gate.get("reply") or "I can only help with SweetCrust Bakery app topics.",
            "language": language,
            "products": [],
            "actions": [{"type": "handover_human"}],
            "quick_replies": _quick_replies(audience),
            "provider": "guardrails",
            "blocked": True,
            "reason": gate.get("reason"),
            "agentic": True,
            "rag_used": False,
            "tools_used": [],
        }

    message = gate.get("text") or message
    run_id = start_run(user_id=user_id, audience=audience, message=message, provider=f"langgraph:{settings.llm_provider}")
    rag_chunks = {"n": 0}

    def on_rag(n: int) -> None:
        rag_chunks["n"] = max(rag_chunks["n"], n)

    tools = build_support_tools(session, user_id, audience=audience, on_rag=on_rag)
    # Seed RAG into first turn so agent always has baseline knowledge
    seed = hybrid_retrieve(session, message)
    system = agentic_system_prompt(audience, user_context + "\n\nSeed RAG:\n" + (seed.get("context") or "—"), language)

    try:
        model = get_chat_model()
        agent = create_react_agent(model, tools, prompt=system, name="sweetcrust_support")
        messages = _history_messages(history) + [HumanMessage(content=message)]
        out = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max(4, settings.ai_agent_max_iterations * 2)},
        )
        final_msgs = out.get("messages") or []
        last_ai = ""
        for m in reversed(final_msgs):
            if isinstance(m, AIMessage) and (m.content and not getattr(m, "tool_calls", None)):
                last_ai = m.content if isinstance(m.content, str) else str(m.content)
                break
            if isinstance(m, AIMessage) and m.content:
                last_ai = m.content if isinstance(m.content, str) else str(m.content)
                break

        tool_names = tool_names_used(tools) or _extract_tool_names_from_messages(final_msgs)
        note_tools(run_id, tool_names, rag_chunks=seed.get("chunk_count") or rag_chunks["n"])

        # Prefer structured JSON if model emitted it; else plain text reply
        parsed = parse_chatbot_output(last_ai)
        reply = filter_ai_reply(parsed.get("reply") or last_ai or "")
        actions = _norm_actions(parsed.get("actions") or [])
        products: list[Product] = []
        query = parsed.get("product_query") or {}
        if isinstance(query, dict) and any(query.get(k) is not None for k in ("q", "eggless", "max_price", "bestseller", "sugar_free")):
            products = _query_products(session, query)
        if not products:
            # scrape product ids from tool transcripts
            for m in final_msgs:
                content = getattr(m, "content", None)
                if isinstance(content, str) and "|" in content:
                    products = _products_from_tool_text(session, content) or products

        if any("HANDOVER" in str(getattr(m, "content", "")) for m in final_msgs) or any(
            k in message.lower() for k in ("talk to", "owner", "human", "call me", "callback")
        ):
            if not any(a.get("type") == "handover_human" for a in actions):
                if any(k in message.lower() for k in ("talk to", "owner", "human", "agent", "call", "बात")):
                    actions.append({"type": "handover_human"})

        if products and not any(a.get("type") == "show_products" for a in actions):
            actions.append({"type": "show_products"})

        result = {
            "reply": reply,
            "language": language,
            "products": _serialize_products(products),
            "actions": actions,
            "quick_replies": _quick_replies(audience),
            "provider": f"langgraph-agentic:{settings.llm_provider}",
            "model": settings.llm_model,
            "blocked": False,
            "agentic": True,
            "rag_used": bool(seed.get("chunk_count") or rag_chunks["n"] or "agentic_rag" in tool_names),
            "tools_used": tool_names,
            "rag_chunks": seed.get("chunk_count") or rag_chunks["n"],
        }
        finish_run(run_id, reply=reply, provider=result["provider"])
        return result
    except Exception as e:
        logger.exception("Agentic LangGraph failed")
        finish_run(run_id, error=str(e))
        raise


def run_chatbot_graph(
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
    audience = _detect_audience(session, user_id, audience)
    user_context = _build_user_context(session, user_id, audience)

    if not settings.llm_configured or (settings.ai_dev_mock_llm and not settings.llm_api_key):
        raise RuntimeError("LLM not configured")

    # Prefer agentic ReAct; fall back to linear RAG graph
    try:
        return run_agentic_chatbot(
            session, user_id, message, language, audience=audience, history=history
        )
    except Exception:
        logger.exception("Agentic path failed — linear LangGraph RAG")

    run_id = start_run(
        user_id=user_id, audience=audience, message=message, provider=f"langgraph-linear:{settings.llm_provider}"
    )
    graph = get_graph()
    state: ChatState = {
        "message": message,
        "language": language,
        "user_id": user_id,
        "audience": audience,
        "user_context": user_context,
        "history": history or [],
    }
    try:
        out = graph.invoke(state)
        parsed = out.get("parsed") or {}
        query = parsed.get("product_query") or {}
        if isinstance(query, dict):
            products = _query_products(session, query)
        else:
            products = _query_products(session, query.model_dump() if hasattr(query, "model_dump") else {})

        actions = _norm_actions(out.get("actions") or [])
        if products and not any(a.get("type") == "show_products" for a in actions):
            actions.append({"type": "show_products"})

        result = {
            "reply": out.get("reply") or "",
            "language": language,
            "products": _serialize_products(products),
            "actions": actions,
            "quick_replies": _quick_replies(audience),
            "provider": out.get("provider") or settings.llm_provider,
            "model": out.get("model") or settings.llm_model,
            "blocked": bool(out.get("blocked")),
            "reason": out.get("block_reason"),
            "rag_used": bool(out.get("rag_context")),
            "agentic": False,
            "tools_used": ["linear_rag"],
        }
        finish_run(run_id, reply=result["reply"], provider=str(result["provider"]), blocked=result["blocked"])
        return result
    except Exception as e:
        finish_run(run_id, error=str(e))
        raise


def _quick_replies(audience: str) -> list[str]:
    if audience == "retailer":
        return [
            "What is my credit balance?",
            "Where is my shop order?",
            "Minimum order qty?",
            "Talk to bakery owner",
        ]
    return [
        "Eggless chocolate cakes",
        "Birthday cake under ₹1000",
        "Where is my order?",
        "Talk to bakery owner",
    ]


def _norm_actions(actions: list) -> list[dict]:
    norm = []
    for a in actions:
        if isinstance(a, dict):
            norm.append(a)
        elif hasattr(a, "model_dump"):
            norm.append(a.model_dump())
        else:
            norm.append({"type": str(a)})
    return norm


def _query_products(session: Session, query: dict) -> list[Product]:
    stmt = select(Product).where(Product.is_active == True, Product.is_draft == False)  # noqa: E712
    if query.get("eggless") is True:
        stmt = stmt.where(Product.is_eggless == True)  # noqa: E712
    if query.get("sugar_free") is True:
        stmt = stmt.where(Product.is_sugar_free == True)  # noqa: E712
    if query.get("bestseller") is True:
        stmt = stmt.where(Product.is_bestseller == True)  # noqa: E712
    if query.get("max_price") is not None:
        try:
            stmt = stmt.where(Product.selling_price <= float(query["max_price"]))
        except (TypeError, ValueError):
            pass
    if query.get("q"):
        like = f"%{str(query['q']).lower()}%"
        from sqlalchemy import func as sa_func

        stmt = stmt.where(sa_func.lower(Product.name).like(like))
    return list(session.exec(stmt.order_by(Product.rating.desc()).limit(5)).all())


def _serialize_products(products: list[Product]) -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "selling_price": p.selling_price,
            "cover_image_url": p.cover_image_url,
            "is_eggless": p.is_eggless,
        }
        for p in products
    ]
