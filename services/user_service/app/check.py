"""Domain OpenAPI check."""
from __future__ import annotations
from pathlib import Path
from app.main import create_app

REQUIRED = {'/api/v1/auth/me', '/health'}

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for d in ("config", "routes", "controllers", "services", "repositories", "producers", "consumers"):
        assert (root / "app" / d).is_dir(), d
    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    me = app.openapi()["paths"]["/api/v1/auth/me"]
    assert "get" in me and "patch" in me, me
    print(f"check_user ok — {len(paths)} paths")

if __name__ == "__main__":
    main()
