"""AI observability — LangSmith tracing + local run ring buffer for admin."""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Optional

from app.config import get_settings

_LOCK = threading.Lock()
_RUNS: deque[dict[str, Any]] = deque(maxlen=200)
_CONFIGURED = False


def configure_tracing() -> dict[str, Any]:
    """Enable LangSmith when LANGSMITH_API_KEY is set. Safe to call many times."""
    global _CONFIGURED
    settings = get_settings()
    status = {
        "langsmith": False,
        "project": getattr(settings, "langsmith_project", None) or "sweetcrust",
        "local_buffer": True,
    }
    key = settings.langsmith_api_key or os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
    if not key:
        _CONFIGURED = True
        return status
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ["LANGCHAIN_API_KEY"] = key
    os.environ["LANGSMITH_API_KEY"] = key
    project = getattr(settings, "langsmith_project", None) or "sweetcrust"
    os.environ.setdefault("LANGCHAIN_PROJECT", project)
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    status["langsmith"] = True
    _CONFIGURED = True
    return status


def start_run(
    *,
    user_id: int,
    audience: str,
    message: str,
    provider: str,
) -> str:
    if not _CONFIGURED:
        configure_tracing()
    run_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _RUNS.appendleft(
            {
                "id": run_id,
                "user_id": user_id,
                "audience": audience,
                "message": (message or "")[:300],
                "provider": provider,
                "status": "running",
                "tools": [],
                "rag_chunks": 0,
                "reply_preview": None,
                "error": None,
                "ms": None,
                "started_at": time.time(),
            }
        )
    return run_id


def note_tools(run_id: str, tool_names: list[str], rag_chunks: int = 0) -> None:
    with _LOCK:
        for r in _RUNS:
            if r["id"] == run_id:
                r["tools"] = tool_names
                r["rag_chunks"] = rag_chunks
                break


def finish_run(
    run_id: str,
    *,
    reply: str = "",
    error: Optional[str] = None,
    provider: Optional[str] = None,
    blocked: bool = False,
) -> None:
    with _LOCK:
        for r in _RUNS:
            if r["id"] == run_id:
                r["status"] = "error" if error else ("blocked" if blocked else "ok")
                r["reply_preview"] = (reply or "")[:240]
                r["error"] = error
                if provider:
                    r["provider"] = provider
                r["ms"] = int((time.time() - r["started_at"]) * 1000)
                break


def recent_runs(limit: int = 40) -> list[dict[str, Any]]:
    with _LOCK:
        rows = list(_RUNS)[:limit]
    out = []
    for r in rows:
        out.append(
            {
                **r,
                "started_at": None,
            }
        )
    return out


def monitor_status() -> dict[str, Any]:
    tracing = configure_tracing()
    with _LOCK:
        n = len(_RUNS)
        ok = sum(1 for r in _RUNS if r["status"] == "ok")
        err = sum(1 for r in _RUNS if r["status"] == "error")
    return {
        **tracing,
        "runs_buffered": n,
        "ok": ok,
        "errors": err,
    }
