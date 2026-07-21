#!/usr/bin/env bash
# Issue / renew Let's Encrypt cert and enable TLS nginx.
# Primary: api.skbakery.in (also covers api.bakerywala.cloud when EXTRA_API_DOMAINS is set).
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

DOMAIN="${API_DOMAIN:-api.skbakery.in}"
# Space-separated extra hostnames on the same cert (optional)
EXTRA_DOMAINS="${EXTRA_API_DOMAINS:-api.bakerywala.cloud}"
EMAIL="${CERTBOT_EMAIL:-}"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.production)

if [[ -z "$EMAIL" || "$EMAIL" == CHANGE_ME@* ]]; then
  echo "Set CERTBOT_EMAIL in .env.production (valid email for Let's Encrypt)." >&2
  exit 1
fi

# Ensure HTTP bootstrap is serving ACME challenges (nginx needs gateway DNS)
cp nginx/nginx.prod.bootstrap.conf nginx/nginx.prod.active.conf
"${COMPOSE[@]}" up -d gateway realtime nginx
for i in $(seq 1 30); do
  if curl -fsS --max-time 2 "http://127.0.0.1/gateway/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if ! curl -fsS --max-time 5 "http://127.0.0.1/gateway/health" >/dev/null; then
  echo "HTTP not reachable on :80 — fix nginx/firewall before certbot." >&2
  "${COMPOSE[@]}" ps nginx gateway realtime
  "${COMPOSE[@]}" logs --tail=40 nginx
  exit 1
fi

CERTBOT_ARGS=(-d "${DOMAIN}")
for d in ${EXTRA_DOMAINS}; do
  [[ -n "$d" && "$d" != "$DOMAIN" ]] && CERTBOT_ARGS+=(-d "$d")
done

echo "Requesting certificate for ${DOMAIN}${EXTRA_DOMAINS:+ (+ ${EXTRA_DOMAINS})}…"
"${COMPOSE[@]}" --profile certbot run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  "${CERTBOT_ARGS[@]}" \
  --email "${EMAIL}" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  --cert-name "${DOMAIN}"

# Point TLS nginx at this cert name
sed -e "s|api\\.skbakery\\.in|${DOMAIN}|g" nginx/nginx.prod.conf > nginx/nginx.prod.active.conf
# Keep both hostnames in server_name if EXTRA set
if [[ -n "${EXTRA_DOMAINS}" ]]; then
  sed -i "s|server_name ${DOMAIN};|server_name ${DOMAIN} ${EXTRA_DOMAINS};|g" nginx/nginx.prod.active.conf
fi
"${COMPOSE[@]}" up -d nginx
"${COMPOSE[@]}" exec -T nginx nginx -t
"${COMPOSE[@]}" exec -T nginx nginx -s reload

echo "TLS enabled → https://${DOMAIN}/gateway/health"
curl -fsS "https://${DOMAIN}/gateway/health" && echo
