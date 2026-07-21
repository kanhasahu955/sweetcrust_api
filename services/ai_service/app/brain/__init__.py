"""SweetCrust AI package (lazy exports)."""

__all__ = [
    "chat_completion",
    "get_chat_model",
    "run_chatbot_graph",
    "retrieve_context",
    "seed_rag_documents",
    "hybrid_retrieve",
    "configure_tracing",
    "recent_runs",
]


def __getattr__(name: str):
    if name in ("chat_completion", "get_chat_model"):
        from app.brain.llm import chat_completion, get_chat_model

        return {"chat_completion": chat_completion, "get_chat_model": get_chat_model}[name]
    if name == "run_chatbot_graph":
        from app.brain.graphs import run_chatbot_graph

        return run_chatbot_graph
    if name in ("retrieve_context", "seed_rag_documents", "hybrid_retrieve"):
        from app.brain import rag

        return getattr(rag, name)
    if name in ("configure_tracing", "recent_runs"):
        from app.brain import monitor

        return getattr(monitor, name)
    raise AttributeError(name)
