#!/usr/bin/env bash
# Align MySQL sweetcrust user password with MYSQL_PASSWORD in .env.production.
# Needed when HOSTINGER_ENV_FILE / sync regenerated MYSQL_* after the volume was first initialized.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env.production
set +a

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.production)
USER_NAME="${MYSQL_USER:-sweetcrust}"

test -n "${MYSQL_ROOT_PASSWORD:-}" || { echo "MYSQL_ROOT_PASSWORD empty" >&2; exit 1; }
test -n "${MYSQL_PASSWORD:-}" || { echo "MYSQL_PASSWORD empty" >&2; exit 1; }

sql_escape() { printf '%s' "$1" | sed "s/'/''/g"; }
U="$(sql_escape "$USER_NAME")"
P="$(sql_escape "$MYSQL_PASSWORD")"
SQL="ALTER USER '${U}'@'%' IDENTIFIED BY '${P}'; FLUSH PRIVILEGES;"

echo "Resetting MySQL user ${USER_NAME} to match .env.production…"
"${COMPOSE[@]}" exec -T \
  -e MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" \
  -e SQL="${SQL}" \
  mysql sh -c 'mysql -uroot -e "$SQL"'

echo "Verifying app login…"
"${COMPOSE[@]}" exec -T \
  -e MYSQL_PWD="${MYSQL_PASSWORD}" \
  -e APP_USER="${USER_NAME}" \
  mysql sh -c 'mysql -u"$APP_USER" -e "SELECT 1 AS ok;"'

echo "Recreating app services…"
"${COMPOSE[@]}" up -d --force-recreate \
  auth catalog cart payment rider ai store_ops user search assortment pricing promotion \
  inventory picking checkout order invoice location dispatch tracking routing notification \
  support rating analytics forecast commerce gateway

echo "Waiting for auth health…"
for _ in $(seq 1 40); do
  if "${COMPOSE[@]}" exec -T gateway wget -qO- --timeout=2 http://auth:8001/health >/dev/null 2>&1; then
    echo "auth OK"
    break
  fi
  sleep 3
done

curl -fsS --max-time 5 http://127.0.0.1/gateway/health && echo
echo "Done."
