"""ponytail: commerce OpenAPI surface + layout. Run: python -m app.check"""
from __future__ import annotations

from pathlib import Path

from app.main import create_app

REQUIRED = {
    "/health",
    "/api/v1/customer/addresses",
    "/api/v1/customer/addresses/{address_id}",
    "/api/v1/customer/cart",
    "/api/v1/customer/cart/items",
    "/api/v1/customer/cart/items/{item_id}",
    "/api/v1/customer/cart/coupon",
    "/api/v1/customer/checkout",
    "/api/v1/customer/orders",
    "/api/v1/customer/orders/{order_id}",
    "/api/v1/customer/orders/{order_id}/track",
    "/api/v1/customer/orders/{order_id}/invoice",
    "/api/v1/customer/orders/{order_id}/cancel",
    "/api/v1/customer/orders/{order_id}/rate",
    "/api/v1/customer/orders/{order_id}/reorder",
    "/api/v1/customer/orders/{order_id}/share-track",
    "/api/v1/customer/custom-cakes",
    "/api/v1/customer/returns",
    "/api/v1/customer/returns/{return_id}",
    "/api/v1/customer/chats",
    "/api/v1/customer/chats/{conversation_id}/messages",
    "/api/v1/customer/notifications",
    "/api/v1/customer/notifications/read",
    "/api/v1/customer/profile/summary",
    "/api/v1/customer/wallet",
    "/api/v1/customer/wallet/add",
    "/api/v1/customer/referral",
    "/api/v1/customer/referral/apply",
    "/api/v1/customer/subscriptions",
    "/api/v1/customer/subscriptions/{plan_id}",
    "/api/v1/customer/gift-hampers",
    "/api/v1/customer/corporate",
    "/api/v1/customer/track/share/{token}",
}

# Owned elsewhere — must NOT appear here
FORBIDDEN = {
    "/api/v1/customer/home",
    "/api/v1/customer/products",
    "/api/v1/customer/products/{product_id}",
    "/api/v1/customer/categories",
    "/api/v1/customer/payments/confirm",
    "/api/v1/customer/payments/methods",
    "/api/v1/customer/delivery/check",
    "/api/v1/customer/ai/chat",
    "/api/v1/customer/faqs",
    "/api/v1/customer/calls",
    "/api/v1/customer/calls/{call_id}",
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
    print(f"check_commerce ok — {len(paths)} paths, commerce_service/main.py + app/")


if __name__ == "__main__":
    main()
