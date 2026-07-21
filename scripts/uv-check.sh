#!/usr/bin/env bash
# Run package + one service OpenAPI check with uv.
# Usage: ./scripts/uv-check.sh [auth_service]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE="${1:-auth_service}"

cd "$ROOT"
uv run --project "$ROOT" python -m package.check_package
export PYTHONPATH="$ROOT:$ROOT/services/$SERVICE"
uv run --project "$ROOT" python -m app.check
