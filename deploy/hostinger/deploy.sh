#!/usr/bin/env bash
# Deploy backend_v2 to Hostinger VPS over SSH/rsync, then compose up.
#
# Laptop (pushes local .env.production):
#   ./deploy/hostinger/deploy.sh
#
# GitHub Actions — dynamic env from secret HOSTINGER_ENV_FILE (written to .env.production before this runs):
#   ./deploy/hostinger/deploy.sh --ci
#
# Already on the server:
#   ./deploy/hostinger/deploy.sh --local
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DEPLOY_HOST="${DEPLOY_HOST:-145.223.21.127}"
DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/sweetcrust/backend_v2}"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.production)
LOCAL=0
CI=0
SKIP_BUILD="${SKIP_BUILD:-0}"

for arg in "$@"; do
  case "$arg" in
    --local) LOCAL=1 ;;
    --ci) CI=1 ;;
    -h|--help)
      echo "Usage: DEPLOY_HOST=… DEPLOY_USER=… $0 [--local|--ci]"
      exit 0
      ;;
  esac
done

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

need_env() {
  if [[ ! -f .env.production ]]; then
    echo "Missing .env.production — set GitHub secret HOSTINGER_ENV_FILE or copy .env.production.example." >&2
    exit 1
  fi
  if grep -q 'CHANGE_ME' .env.production; then
    echo "WARNING: .env.production still contains CHANGE_ME placeholders." >&2
  fi
}

ensure_active_nginx() {
  if [[ ! -f nginx/nginx.prod.active.conf ]]; then
    cp nginx/nginx.prod.bootstrap.conf nginx/nginx.prod.active.conf
  fi
  if [[ -f nginx/certbot/conf/live/api.bakerywala.cloud/fullchain.pem ]]; then
    cp nginx/nginx.prod.conf nginx/nginx.prod.active.conf
  fi
}

compose_up() {
  need_env
  ensure_active_nginx
  mkdir -p nginx/certbot/www nginx/certbot/conf
  "${COMPOSE[@]}" pull redis mysql nginx 2>/dev/null || true
  if [[ "$SKIP_BUILD" == "1" ]]; then
    "${COMPOSE[@]}" up -d --remove-orphans
  else
    "${COMPOSE[@]}" up -d --build --remove-orphans
  fi
  echo "Waiting for gateway health…"
  for _ in $(seq 1 60); do
    if curl -fsS http://127.0.0.1/gateway/health >/dev/null 2>&1; then
      echo "OK http://127.0.0.1/gateway/health"
      return 0
    fi
    sleep 3
  done
  echo "Health check timed out — run: ${COMPOSE[*]} logs --tail=80" >&2
  return 1
}

rsync_code() {
  rsync -az --delete \
    --exclude '.venv/' \
    --exclude 'node_modules/' \
    --exclude 'logs/' \
    --exclude 'uploads/' \
    --exclude '.git/' \
    --exclude '**/__pycache__/' \
    --exclude '**/*.pyc' \
    --exclude 'gateway/node_modules/' \
    --exclude 'realtime/node_modules/' \
    --exclude '.env' \
    --exclude '.env.production' \
    --exclude '.env.production.local' \
    --exclude 'nginx/certbot/conf/' \
    --exclude 'nginx/certbot/www/' \
    ./ "${REMOTE}:${DEPLOY_PATH}/"
}

upload_env() {
  need_env
  echo "Uploading .env.production → ${REMOTE}:${DEPLOY_PATH}/"
  scp -q .env.production "${REMOTE}:${DEPLOY_PATH}/.env.production"
  ssh "${REMOTE}" "chmod 600 '${DEPLOY_PATH}/.env.production'"
}

remote_compose() {
  ssh "${REMOTE}" "bash -s" <<EOF
set -euo pipefail
cd '${DEPLOY_PATH}'
chmod +x deploy/hostinger/*.sh
if ! command -v docker >/dev/null; then
  bash deploy/hostinger/setup-vps.sh
fi
if [[ ! -f .env.production ]]; then
  echo "Server missing ${DEPLOY_PATH}/.env.production — add GitHub secret HOSTINGER_ENV_FILE and redeploy." >&2
  exit 1
fi
SKIP_BUILD='${SKIP_BUILD}' ./deploy/hostinger/deploy.sh --local
EOF
}

if [[ "$LOCAL" -eq 1 ]]; then
  compose_up
  exit $?
fi

echo "Rsync → ${REMOTE}:${DEPLOY_PATH}"
ssh -o StrictHostKeyChecking=accept-new "${REMOTE}" "mkdir -p '${DEPLOY_PATH}'"
rsync_code

if [[ -f .env.production ]]; then
  upload_env
elif [[ "$CI" -eq 1 ]]; then
  echo "CI: no .env.production on runner — keeping existing file on VPS (if any)"
else
  echo "Missing local .env.production" >&2
  exit 1
fi

remote_compose

echo "Deploy finished. Issue TLS if needed:"
echo "  ssh ${REMOTE} 'cd ${DEPLOY_PATH} && ./deploy/hostinger/issue-cert.sh'"
echo "Health: http://${DEPLOY_HOST}/gateway/health  →  https://api.bakerywala.cloud/gateway/health"
