"""ponytail: AI OpenAPI surface + layout sanity. Run: python -m app.check"""
from __future__ import annotations

from pathlib import Path

from app.main import create_app

REQUIRED = {
    "/api/v1/customer/ai/chat",
    "/api/v1/customer/ai/conversations/{conversation_id}/messages",
    "/api/v1/customer/faqs",
    "/api/v1/customer/calls",
    "/api/v1/admin/calls/ai-outbound",
    "/api/v1/admin/chatbot/faqs",
    "/api/v1/admin/insights",
    "/api/v1/admin/returns/ai-assess",
    "/api/v1/retailer/ai/chat",
    "/api/v1/voice/twilio/voice",
    "/api/v1/ai/status",
    "/health",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]  # ai_service/
    assert (root / "main.py").is_file()
    assert (root / "app").is_dir()
    assert (root / "app" / "config").is_dir()
    assert (root / "app" / "routes").is_dir()
    assert (root / "app" / "controllers").is_dir()
    assert (root / "app" / "services").is_dir()
    assert (root / "app" / "repositories").is_dir()
    assert (root / "app" / "producers").is_dir()
    assert (root / "app" / "consumers").is_dir()
    assert not (root / "models").exists(), "models/ must live under app/"
    assert not (root / "api.py").exists(), "api.py must live under app/"
    assert not (root / "sweetcrust_ai").exists()

    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    assert "/api/v1/customer/cart" not in paths
    print(f"check_ai ok — {len(paths)} paths, ai_service/main.py + app/")


if __name__ == "__main__":
    main()
