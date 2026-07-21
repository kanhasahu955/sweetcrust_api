#!/usr/bin/env bash
# Usage: ./scripts/dev-service.sh auth_service 8001
#        ./scripts/dev-service.sh ai_service 8006
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE="${1:?service}"
PORT="${2:?port}"

# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh" "$ROOT/.env"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install: https://docs.astral.sh/uv/" >&2
  exit 1
fi

export PYTHONPATH="$ROOT:$ROOT/services/$SERVICE${PYTHONPATH:+:$PYTHONPATH}"
export SERVICE_PORT="$PORT"
cd "$ROOT/services/$SERVICE"

# uv manages the environment (.venv under backend_v2 via --project)
exec uv run --project "$ROOT" uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
