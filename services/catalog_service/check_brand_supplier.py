"""Self-check: supplier brand fields resolve correctly.

Run: cd backend_v2 && uv run python services/catalog_service/check_brand_supplier.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.products import resolve_brand_fields  # noqa: E402


def main() -> None:
    brand, sid = resolve_brand_fields(None, 42, shop_name="Sahu Kirana & Sweets")
    assert brand == "Sahu Kirana & Sweets" and sid == 42

    brand, sid = resolve_brand_fields("  Custom Brand  ", 7, shop_name="Ignored Shop")
    assert brand == "Custom Brand" and sid == 7

    brand, sid = resolve_brand_fields("Loose Brand", None)
    assert brand == "Loose Brand" and sid is None

    brand, sid = resolve_brand_fields(None, None)
    assert brand is None and sid is None

    print("ok: resolve_brand_fields")


if __name__ == "__main__":
    main()
