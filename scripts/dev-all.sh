#!/usr/bin/env bash
# Run ALL SweetCrust services locally — no Docker.
#
#   ./scripts/dev-all.sh
#   ./scripts/dev-all.sh --no-ai
#   make up
#
# Needs: uv, Node/npm, Redis (brew install redis), backend_v2/.env
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NO_AI=0
for arg in "$@"; do
  case "$arg" in
    --no-ai) NO_AI=1 ;;
    --docker)
      echo "This script is Docker-free. Use: docker compose up --build" >&2
      exit 1
      ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
  esac
done

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy .env.example → .env first." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for gateway + realtime." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh" "$ROOT/.env"

# Always use host Redis for native run (never docker hostname)
export REDIS_URL="redis://127.0.0.1:6379/0"

mkdir -p "$ROOT/logs"
PIDS=()

cleanup() {
  echo ""
  echo "Stopping services…"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    kill -- -"$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "All stopped."
}
trap cleanup EXIT INT TERM

ensure_redis() {
  if command -v redis-cli >/dev/null 2>&1 && redis-cli -h 127.0.0.1 ping 2>/dev/null | grep -q PONG; then
    echo "redis: up on :6379"
    return 0
  fi

  # Start local redis-server (Homebrew / apt) — never Docker
  if command -v redis-server >/dev/null 2>&1; then
    redis-server --daemonize yes --port 6379 --bind 127.0.0.1
    sleep 0.4
    if redis-cli -h 127.0.0.1 ping 2>/dev/null | grep -q PONG; then
      echo "redis: started redis-server on :6379"
      return 0
    fi
  fi

  echo "Redis not running on 127.0.0.1:6379" >&2
  echo "Install & start (no Docker):" >&2
  echo "  brew install redis && brew services start redis" >&2
  echo "  # or: redis-server --daemonize yes" >&2
  exit 1
}

ensure_node() {
  local dir="$1"
  if [[ ! -d "$ROOT/$dir/node_modules" ]]; then
    echo "npm install → $dir"
    (cd "$ROOT/$dir" && npm install --silent)
  fi
}

start_py() {
  local name="$1" port="$2"
  local log="$ROOT/logs/${name}.log"
  (
    export PYTHONPATH="$ROOT:$ROOT/services/${name}"
    export SERVICE_PORT="$port"
    export PORT="$port"
    export REDIS_URL
    cd "$ROOT/services/${name}"
    exec uv run --project "$ROOT" uvicorn main:app --host 0.0.0.0 --port "$port" --reload
  ) >"$log" 2>&1 &
  PIDS+=($!)
  printf '  :%-5s %s\n' "$port" "$name"
}

start_node() {
  local dir="$1" port="$2" script="$3"
  local log="$ROOT/logs/${dir}.log"
  (
    export PORT="$port"
    export REDIS_URL
    export JWT_SECRET_KEY="${JWT_SECRET_KEY:-}"
    cd "$ROOT/$dir"
    exec npm run "$script"
  ) >"$log" 2>&1 &
  PIDS+=($!)
  printf '  :%-5s %s\n' "$port" "$dir"
}

echo "SweetCrust local (no Docker) → $ROOT"
ensure_redis

echo "uv sync…"
if [[ "$NO_AI" -eq 1 ]]; then
  uv sync --quiet
else
  uv sync --extra ai --quiet
fi
ensure_node gateway
ensure_node realtime

echo "FastAPI…"
start_py auth_service 8001
start_py catalog_service 8002
start_py cart_service 8003
start_py payment_service 8004
start_py rider_service 8005
if [[ "$NO_AI" -eq 0 ]]; then
  start_py ai_service 8006
fi
start_py store_ops_service 8007
start_py user_service 8008
start_py search_service 8009
start_py assortment_service 8010
start_py pricing_service 8011
start_py promotion_service 8012
start_py inventory_service 8013
start_py picking_service 8014
start_py checkout_service 8015
start_py order_service 8016
start_py invoice_service 8017
start_py location_service 8018
start_py dispatch_service 8019
start_py tracking_service 8020
start_py routing_service 8021
start_py notification_service 8022
start_py support_service 8023
start_py rating_service 8024
start_py analytics_service 8025
start_py forecast_service 8026
start_py commerce_service 8027

echo "Edge…"
start_node gateway 8080 dev
start_node realtime 8081 dev

echo ""
echo "Ready — Ctrl+C stops everything"
echo "  API     http://127.0.0.1:8080"
echo "  Socket  http://127.0.0.1:8081/health"
echo "  Logs    $ROOT/logs/"
echo ""

wait
