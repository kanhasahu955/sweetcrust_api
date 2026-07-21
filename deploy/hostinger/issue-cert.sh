#!/usr/bin/env bash
# Issue / renew Let's Encrypt cert for api.bakerywala.cloud and enable TLS nginx.
# Run on the VPS from /opt/sweetcrust/backend_v2 after HTTP stack is up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f .env.production ]]; then
  # shellcheck disable=SC1091
  set -a
  # shellcheck disable=SC1091
  source .env.production
  set +a
fi

DOMAIN="${API_DOMAIN:-api.bakerywala.cloud}"
EMAIL="${CERTBOT_EMAIL:-}"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.production)

if [[ -z "$EMAIL" || "$EMAIL" == CHANGE_ME@* ]]; then
  echo "Set CERTBOT_EMAIL in .env.production (valid email for Let's Encrypt)." >&2
  exit 1
fi

# Ensure HTTP bootstrap is serving ACME challenges
cp nginx/nginx.prod.bootstrap.conf nginx/nginx.prod.active.conf
"${COMPOSE[@]}" up -d nginx
"${COMPOSE[@]}" exec -T nginx nginx -s reload 2>/dev/null || "${COMPOSE[@]}" restart nginx

echo "Requesting certificate for ${DOMAIN}…"
"${COMPOSE[@]}" --profile certbot run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "${DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --no-eff-email \
  --non-interactive

cp nginx/nginx.prod.conf nginx/nginx.prod.active.conf
"${COMPOSE[@]}" up -d nginx
"${COMPOSE[@]}" exec -T nginx nginx -t
"${COMPOSE[@]}" exec -T nginx nginx -s reload

echo "TLS enabled → https://${DOMAIN}/gateway/health"
curl -fsS "https://${DOMAIN}/gateway/health" && echo
