"""ponytail: admin OpenAPI surface + layout. Run: python -m app.check"""
from __future__ import annotations

from pathlib import Path

from app.main import create_app

REQUIRED = {
    "/api/v1/admin/dashboard",
    "/api/v1/admin/orders",
    "/api/v1/admin/orders/{order_id}/status",
    "/api/v1/admin/orders/{order_id}/invoice",
    "/api/v1/admin/orders/{order_id}/payment-link",
    "/api/v1/admin/products",
    "/api/v1/admin/products/{product_id}/duplicate",
    "/api/v1/admin/products/ai-upload/publish",
    "/api/v1/admin/categories",
    "/api/v1/admin/shops",
    "/api/v1/admin/shops/{retailer_user_id}/ledger",
    "/api/v1/admin/shops/{retailer_user_id}/collect",
    "/api/v1/admin/purchases",
    "/api/v1/admin/purchases/{purchase_id}/pay",
    "/api/v1/admin/payments/{payment_id}/refund",
    "/api/v1/admin/customers/{customer_id}/presence",
    "/api/v1/admin/reports",
    "/api/v1/admin/integrations/check",
    "/api/v1/admin/custom-cakes",
    "/api/v1/admin/custom-cakes/{req_id}",
    "/api/v1/admin/delivery/persons",
    "/api/v1/admin/coupons",
    "/api/v1/admin/banners",
    "/api/v1/admin/settings",
    "/api/v1/admin/tickets",
    "/api/v1/retailer/me",
    "/api/v1/retailer/catalog",
    "/api/v1/retailer/products/request",
    "/api/v1/retailer/orders",
    "/api/v1/retailer/orders/{order_id}",
    "/api/v1/retailer/chats",
    "/api/v1/retailer/chats/support",
    "/api/v1/retailer/chats/{conversation_id}/messages",
    "/api/v1/retailer/calls/callback",
    "/api/v1/uploads",
    "/api/v1/uploads/credentials/check",
    "/uploads/credentials/check",
    "/health",
}

# AI owns these — must NOT appear here
FORBIDDEN = {
    "/api/v1/admin/insights",
    "/api/v1/admin/chatbot/faqs",
    "/api/v1/admin/returns/ai-assess",
    "/api/v1/admin/calls/ai-outbound",
    "/api/v1/admin/products/ai-upload",
    "/api/v1/admin/categories/ai-image",
    "/api/v1/admin/coupons/ai-suggest",
    "/api/v1/retailer/ai/chat",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
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

    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    leaked = sorted(FORBIDDEN & paths)
    assert not leaked, leaked
    print(f"check_admin ok — {len(paths)} paths, admin_service/main.py + app/")


if __name__ == "__main__":
    main()
