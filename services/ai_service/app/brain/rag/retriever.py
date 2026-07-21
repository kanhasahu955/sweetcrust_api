"""RAG retriever — BM25 local index; optional Pinecone when configured."""

from __future__ import annotations

from package.logger import get_logger
from functools import lru_cache
from typing import Optional

from langchain_core.documents import Document

from app.brain.rag.documents import BAKERY_DOCS
from app.config import get_settings

logger = get_logger(__name__)


@lru_cache
def _bm25_retriever():
    from langchain_community.retrievers import BM25Retriever

    docs = [Document(page_content=d["text"], metadata={"id": d["id"]}) for d in BAKERY_DOCS]
    retriever = BM25Retriever.from_documents(docs)
    settings = get_settings()
    retriever.k = settings.rag_top_k
    return retriever


def seed_rag_documents(extra: Optional[list[dict[str, str]]] = None) -> int:
    """Reset BM25 cache so new docs can be picked up after process restart."""
    _bm25_retriever.cache_clear()
    count = len(BAKERY_DOCS) + (len(extra) if extra else 0)
    if extra:
        BAKERY_DOCS.extend(extra)
        _bm25_retriever.cache_clear()
    return count


def retrieve_context(query: str, k: Optional[int] = None) -> str:
    settings = get_settings()
    top_k = k or settings.rag_top_k
    # Prefer Pinecone when fully configured; fall back to BM25
    pinecone_bits = _pinecone_retrieve(query, top_k)
    if pinecone_bits:
        return pinecone_bits
    try:
        retriever = _bm25_retriever()
        retriever.k = top_k
        docs = retriever.invoke(query)
        if not docs:
            return ""
        return "\n\n".join(f"- {d.page_content}" for d in docs)
    except Exception:
        logger.exception("BM25 retrieve failed")
        return ""


def _pinecone_retrieve(query: str, k: int) -> str:
    settings = get_settings()
    if settings.vector_store.lower() != "pinecone" or not settings.pinecone_api_key:
        return ""
    if not settings.openai_api_key and settings.embedding_provider == "openai":
        return ""
    try:
        # Soft integration — skip silently if pinecone package / index missing
        from pinecone import Pinecone  # type: ignore

        # Without indexed bakery vectors yet, return empty so BM25 handles RAG
        _ = Pinecone(api_key=settings.pinecone_api_key)
        logger.debug("Pinecone client ready; using BM25 until bakery vectors are upserted")
        return ""
    except Exception:
        return ""
