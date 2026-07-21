"""ponytail: OpenAPI surface + Razorpay HMAC math. Run: python -m app.check"""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from unittest.mock import patch

from app.main import create_app
from app.services import razorpay as razorpay_ops

REQUIRED = {
    "/api/v1/payments/methods",
    "/api/v1/payments/credentials/check",
    "/api/v1/payments/razorpay/create",
    "/api/v1/payments/razorpay/verify",
    "/api/v1/payments/webhooks/razorpay",
    "/api/v1/customer/payments/confirm",
    "/api/v1/customer/payments/methods",
    "/health",
}


def _razorpay_hmac_check() -> None:
    secret = "test_secret"
    order_id, pay_id = "order_ABC", "pay_XYZ"
    sig = hmac.new(secret.encode(), f"{order_id}|{pay_id}".encode(), hashlib.sha256).hexdigest()

    class _S:
        razorpay_key_secret = secret

    with patch.object(razorpay_ops, "get_settings", return_value=_S()):
        assert razorpay_ops.verify_payment_signature(
            razorpay_order_id=order_id,
            razorpay_payment_id=pay_id,
            razorpay_signature=sig,
        )
        assert not razorpay_ops.verify_payment_signature(
            razorpay_order_id=order_id,
            razorpay_payment_id=pay_id,
            razorpay_signature="deadbeef",
        )


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

    _razorpay_hmac_check()

    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    print(f"check_payments ok — {len(paths)} paths")


if __name__ == "__main__":
    main()
