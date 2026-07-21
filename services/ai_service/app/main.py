"""AI FastAPI app — async OOP (LLM stays sync-ish via run_sync / to_thread)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import app.models  # noqa: F401 — register tables before init_db
from app import routes
from app.config import boot_settings, get_settings
from package.common.factory import create_service_app
from package.common.lifecycle import service_lifespan
from package.common.schemas import HealthOut
from package.database import init_db, ping_async_db, ping_db, pool_status, session_scope
from package.logger import get_logger
from package.redis import redis_ping

logger = get_logger("ai")

boot_settings()


def _seed_default_faqs() -> None:
    from sqlmodel import select

    from app.models.ops import ChatbotFAQ

    defaults = [
        (
            "How does shop credit / udhaar work?",
            "Approved shops get a credit limit set by the bakery owner. Outstanding balance shows in the shop app.",
        ),
        (
            "What is the minimum order quantity?",
            "Each catalog product shows its MOQ. Order at least that many units per SKU.",
        ),
        (
            "How do I talk to the bakery owner?",
            "Open Chat → Owner, or ask the assistant to talk to the owner.",
        ),
        (
            "Where is my order?",
            "Open Orders in the app for status, or ask the assistant.",
        ),
    ]
    with session_scope() as session:
        existing = {(f.question or "").strip().lower() for f in session.exec(select(ChatbotFAQ)).all()}
        added = 0
        for q, a in defaults:
            if q.lower() in existing:
                continue
            session.add(ChatbotFAQ(question=q, answer=a, language="en", is_active=True))
            added += 1
        if added:
            logger.info("Seeded %s default FAQs", added)


def _ai_startup() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.vector_store_path).mkdir(parents=True, exist_ok=True)
    init_db()
    try:
        from app.brain.monitor import configure_tracing
        from app.brain.rag import seed_rag_documents
        from app.brain.rag.pipeline import ensure_retailer_docs_seeded

        n = seed_rag_documents()
        ensure_retailer_docs_seeded()
        configure_tracing()
        _seed_default_faqs()
        logger.info("RAG ready (%s docs)", n)
    except Exception:
        logger.exception("RAG/FAQ seed skipped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    boot_settings()
    st = get_settings().integration_status()
    async with service_lifespan(
        app,
        service="ai",
        version=get_settings().service_version,
        on_startup=_ai_startup,
        extra={
            "llm": st.get("llm"),
            "vector_store": st.get("vector_store"),
            "twilio_voice": st.get("twilio_voice"),
            "guardrails": st.get("guardrails"),
        },
    ):
        yield


def create_app() -> FastAPI:
    boot_settings()
    app = create_service_app(
        title="SweetCrust AI",
        version=get_settings().service_version,
        description="Chatbot, RAG, vision, Twilio voice (async OOP)",
        lifespan=lifespan,
    )
    routes.mount(app)

    @app.get("/health", response_model=HealthOut)
    async def health():
        db_ok = ping_db()
        try:
            async_ok = await ping_async_db()
        except Exception:
            async_ok = False
        try:
            redis_ok = bool(redis_ping())
        except Exception:
            redis_ok = False
        st = get_settings().integration_status()
        return HealthOut(
            service="ai",
            ok=db_ok,
            database=db_ok,
            redis=redis_ok,
            status="running" if db_ok else "degraded",
            details={
                "llm": st.get("llm"),
                "vector_store": st.get("vector_store"),
                "twilio_voice": st.get("twilio_voice"),
                "pool": pool_status(),
                "async_db": async_ok,
            },
        )

    return app


app = create_app()
