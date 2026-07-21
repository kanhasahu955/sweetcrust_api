"""Hybrid + agentic RAG: BM25 bakery docs + admin FAQs + light query expansion."""

from __future__ import annotations

from package.logger import get_logger
import re
from typing import Any, Optional

from sqlmodel import Session, select

from app.brain.rag.retriever import retrieve_context, seed_rag_documents
from app.config import get_settings

logger = get_logger(__name__)

_SYNONYMS = {
    "udhaar": "credit shop balance outstanding",
    "credit": "udhaar outstanding credit limit",
    "gst": "invoice tax gstin",
    "moq": "minimum order quantity",
    "delivery": "dispatch rider delivery eta",
    "refund": "return damaged replacement",
    "eggless": "without egg eggless cake",
}


def expand_query(query: str) -> str:
    """Cheap agentic rewrite — expand domain synonyms without an extra LLM hop."""
    q = (query or "").strip()
    extra: list[str] = []
    low = q.lower()
    for key, expand in _SYNONYMS.items():
        if key in low:
            extra.append(expand)
    return f"{q} {' '.join(extra)}".strip()


def faq_chunks(session: Session, query: str, k: int = 3) -> list[dict[str, Any]]:
    from app.models.ops import ChatbotFAQ

    faqs = list(session.exec(select(ChatbotFAQ).where(ChatbotFAQ.is_active == True)).all())  # noqa: E712
    if not faqs:
        return []
    tokens = {t for t in re.split(r"\W+", query.lower()) if len(t) > 2}
    scored: list[tuple[int, Any]] = []
    for faq in faqs:
        q = (faq.question or "").lower()
        a = (faq.answer or "").lower()
        q_tokens = {t for t in re.split(r"\W+", q) if len(t) > 2}
        score = len(tokens & q_tokens)
        if q and q in query.lower():
            score += 5
        for t in tokens:
            if t in a:
                score += 1
        if score > 0:
            scored.append((score, faq))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, faq in scored[:k]:
        out.append(
            {
                "source": "faq",
                "id": f"faq-{faq.id}",
                "score": score,
                "text": f"Q: {faq.question}\nA: {faq.answer}",
            }
        )
    return out


def policy_chunks(query: str, k: Optional[int] = None) -> list[dict[str, Any]]:
    settings = get_settings()
    top_k = k or settings.rag_top_k
    expanded = expand_query(query)
    raw = retrieve_context(expanded, k=top_k)
    if not raw:
        return []
    chunks = []
    for i, part in enumerate(raw.split("\n\n")):
        text = part.lstrip("- ").strip()
        if text:
            chunks.append({"source": "policy", "id": f"policy-{i}", "score": top_k - i, "text": text})
    return chunks


def hybrid_retrieve(session: Session, query: str, k: Optional[int] = None) -> dict[str, Any]:
    """Agentic RAG retrieve step: expand → FAQ + policy → merge."""
    settings = get_settings()
    top_k = k or settings.rag_top_k
    expanded = expand_query(query)
    faqs = faq_chunks(session, expanded, k=min(3, top_k))
    policies = policy_chunks(expanded, k=top_k)
    merged = faqs + policies
    # Prefer FAQ hits, then policies
    merged.sort(key=lambda c: (0 if c["source"] == "faq" else 1, -int(c.get("score") or 0)))
    merged = merged[: top_k + 2]
    context = "\n\n".join(f"[{c['source']}] {c['text']}" for c in merged)
    return {
        "query": query,
        "expanded_query": expanded,
        "chunks": merged,
        "context": context,
        "chunk_count": len(merged),
    }


def ensure_retailer_docs_seeded() -> None:
    """Idempotent: add B2B policy docs if missing (process lifetime)."""
    from app.brain.rag import documents as docs_mod

    ids = {d["id"] for d in docs_mod.BAKERY_DOCS}
    extras = [
        {
            "id": "b2b-credit",
            "text": (
                "Village shop (retailer) credit / udhaar: approved shops get a credit limit set by the bakery owner. "
                "Outstanding balance is shown in the shop app. Payments can be credit, COD, or UPI. "
                "Blocked shops cannot place new orders until the owner clears dues."
            ),
        },
        {
            "id": "b2b-ordering",
            "text": (
                "Retailers order from the SweetCrust wholesale catalog. Each product shows shop price, description, "
                "images, and minimum order quantity (MOQ). Suggest new products with photos; owner publishes drafts."
            ),
        },
        {
            "id": "b2b-support",
            "text": (
                "Shops can chat with the bakery owner, use the AI assistant, upload photos, and request a phone callback. "
                "Offline messages are delivered when the other party comes online."
            ),
        },
    ]
    added = [e for e in extras if e["id"] not in ids]
    if added:
        seed_rag_documents(added)
