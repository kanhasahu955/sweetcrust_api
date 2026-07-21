"""Domain OpenAPI check."""
from __future__ import annotations
from pathlib import Path
from app.main import create_app

REQUIRED = {'/api/v1/delivery/me', '/health'}

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for d in ("config", "routes", "controllers", "services", "repositories", "producers", "consumers"):
        assert (root / "app" / d).is_dir(), d
    paths = set(create_app().openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    print(f"check_rider ok — {len(paths)} paths")

if __name__ == "__main__":
    main()
