"""LangChain chat model factory + thin chat_completion helper."""

from __future__ import annotations

import json
from package.logger import get_logger
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import get_settings

logger = get_logger(__name__)


def get_chat_model(
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    settings = get_settings()
    temp = temperature if temperature is not None else settings.llm_temperature
    tokens = max_tokens or settings.rag_max_tokens
    provider = settings.llm_provider.lower()

    if provider == "groq" or (provider not in ("openai", "google", "gemini", "anthropic") and settings.groq_api_key):
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=settings.groq_api_key or settings.llm_api_key,
            model=settings.llm_model,
            temperature=temp,
            max_tokens=tokens,
        )

    if provider == "openai" or settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.llm_model if provider == "openai" else "gpt-4o-mini",
            temperature=temp,
            max_tokens=tokens,
        )

    # Fallback: Groq if key exists
    if settings.groq_api_key:
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.llm_model,
            temperature=temp,
            max_tokens=tokens,
        )

    raise RuntimeError("No LangChain chat model configured (set GROQ_API_KEY or OPENAI_API_KEY)")


def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    json_mode: bool = False,
) -> str:
    """Backward-compatible helper used by agents/graphs."""
    settings = get_settings()
    if settings.ai_dev_mock_llm and settings.is_dev and not settings.llm_api_key:
        return _mock_reply(messages)

    lc_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))

    model = get_chat_model(temperature=temperature, max_tokens=max_tokens)
    if json_mode and hasattr(model, "bind"):
        try:
            model = model.bind(response_format={"type": "json_object"})
        except Exception:
            pass
    result = model.invoke(lc_messages)
    content = result.content
    if isinstance(content, list):
        # some providers return content blocks
        parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _mock_reply(messages: list[dict[str, str]]) -> str:
    last = messages[-1]["content"] if messages else ""
    return json.dumps(
        {
            "reply": f"(mock) Thanks for asking about: {last[:120]}",
            "actions": [{"type": "show_products"}],
            "product_query": {"eggless": None, "max_price": None, "bestseller": True},
        }
    )
