#!/usr/bin/env bash
# Take local backend_v2/.env → apply production overlays → upload as GitHub secret HOSTINGER_ENV_FILE.
# Every Deploy Action then writes that file to the VPS as .env.production.
#
#   cd backend_v2
#   ./deploy/hostinger/sync-env-to-github.sh
#   ./deploy/hostinger/sync-env-to-github.sh --email you@example.com
#   git push origin main   # triggers deploy with the synced env
#
# Requires: gh auth login
# Never commits .env (gitignored).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

REPO="${GITHUB_REPOSITORY:-kanhasahu955/sweetcrust_api}"
SRC="${ENV_SRC:-.env}"
EMAIL=""
SSH_KEY_FILE="${HOSTINGER_SSH_KEY_FILE:-$HOME/.ssh/hostinger_gha}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email=*) EMAIL="${1#*=}"; shift ;;
    --email) EMAIL="${2:-}"; shift 2 ;;
    --src=*) SRC="${1#*=}"; shift ;;
    --src) SRC="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--email you@domain.com] [--src .env]"
      exit 0
      ;;
    *.env*|.*)
      # positional path: ./sync-env-to-github.sh .env
      SRC="$1"; shift
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC — create it or pass --src path" >&2
  exit 1
fi
if ! command -v gh >/dev/null; then
  echo "Install GitHub CLI: brew install gh && gh auth login" >&2
  exit 1
fi
gh auth status >/dev/null

rand() { openssl rand -base64 32 | tr -d '/+=' | head -c 40; }

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# Copy source .env (strip CR)
tr -d '\r' <"$SRC" >"$TMP"

# Ensure MySQL app password exists (needed for Docker mysql service)
if ! grep -qE '^MYSQL_PASSWORD=.+' "$TMP"; then
  echo "MYSQL_PASSWORD=$(rand)" >>"$TMP"
fi
if ! grep -qE '^MYSQL_ROOT_PASSWORD=.+' "$TMP"; then
  echo "MYSQL_ROOT_PASSWORD=$(rand)" >>"$TMP"
fi
if ! grep -qE '^MYSQL_USER=.+' "$TMP"; then
  echo "MYSQL_USER=sweetcrust" >>"$TMP"
fi
if ! grep -qE '^MYSQL_DATABASE=.+' "$TMP"; then
  echo "MYSQL_DATABASE=sweetcrust" >>"$TMP"
fi
if ! grep -qE '^JWT_SECRET_KEY=.+' "$TMP"; then
  echo "JWT_SECRET_KEY=$(rand)$(rand)" >>"$TMP"
fi
if [[ -n "$EMAIL" ]]; then
  if grep -qE '^CERTBOT_EMAIL=' "$TMP"; then
    sed -i.bak 's/^CERTBOT_EMAIL=.*/CERTBOT_EMAIL='"$EMAIL"'/' "$TMP" && rm -f "$TMP.bak"
  else
    echo "CERTBOT_EMAIL=$EMAIL" >>"$TMP"
  fi
elif ! grep -qE '^CERTBOT_EMAIL=.+' "$TMP"; then
  echo "CERTBOT_EMAIL=support@bakerywala.cloud" >>"$TMP"
fi

# Production overlays (rewrite known keys; append if missing)
python3 - "$TMP" <<'PY'
import re, sys, urllib.parse
path = sys.argv[1]
text = open(path, encoding="utf-8").read().splitlines()

def get(key, default=""):
    for line in text:
        m = re.match(rf'^{re.escape(key)}=(.*)$', line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return default

mysql_user = get("MYSQL_USER", "sweetcrust") or "sweetcrust"
mysql_pass = get("MYSQL_PASSWORD") or get("MYSQL_ROOT_PASSWORD")
mysql_db = get("MYSQL_DATABASE", "sweetcrust") or "sweetcrust"
enc = urllib.parse.quote(mysql_pass, safe="") if mysql_pass else ""
database_url = f"mysql+pymysql://{mysql_user}:{enc}@mysql:3306/{mysql_db}" if enc else get("DATABASE_URL")

overrides = {
    "ENV": "production",
    "RELOAD": "false",
    "LOG_JSON": "true",
    "OTP_DEV_CODE": "",
    "AI_DEV_MOCK_LLM": "false",
    "REDIS_URL": "redis://redis:6379/0",
    "AUTH_PUBLIC_BASE_URL": "https://api.bakerywala.cloud",
    "DATABASE_URL": database_url,
    "CORS_ORIGINS": get("CORS_ORIGINS") if get("CORS_ORIGINS") not in ("", "*") else
        "https://admin.bakerywala.cloud,https://store.bakerywala.cloud,https://bakerywala.cloud,https://www.bakerywala.cloud",
    "API_DOMAIN": get("API_DOMAIN") or "api.bakerywala.cloud",
    "DEPLOY_HOST": get("DEPLOY_HOST") or "145.223.21.127",
    "DEPLOY_USER": get("DEPLOY_USER") or "root",
    "DEPLOY_PATH": get("DEPLOY_PATH") or "/opt/sweetcrust/backend_v2",
}

seen = set()
out = []
for line in text:
    if not line.strip() or line.lstrip().startswith("#"):
        out.append(line)
        continue
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
    if not m:
        out.append(line)
        continue
    k = m.group(1)
    seen.add(k)
    if k in overrides:
        out.append(f"{k}={overrides[k]}")
    else:
        out.append(line)

for k, v in overrides.items():
    if k not in seen:
        out.append(f"{k}={v}")

open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"prepared {sum(1 for l in out if re.match(r'^[A-Za-z_]', l))} keys for production")
PY

# Upload full file as one secret (all keys from your .env + overlays)
gh secret set HOSTINGER_ENV_FILE --repo "$REPO" <"$TMP"
echo "set HOSTINGER_ENV_FILE from $SRC → $REPO"

# Keep deploy SSH secrets in sync too
gh secret set HOSTINGER_HOST --repo "$REPO" --body "${HOSTINGER_HOST:-145.223.21.127}"
gh secret set HOSTINGER_USER --repo "$REPO" --body "${HOSTINGER_USER:-root}"
if [[ -f "$SSH_KEY_FILE" ]]; then
  gh secret set HOSTINGER_SSH_KEY --repo "$REPO" <"$SSH_KEY_FILE"
  echo "set HOSTINGER_SSH_KEY from $SSH_KEY_FILE"
fi

KEYS="$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$TMP" || true)"
echo
echo "Synced ${KEYS} env keys into GitHub secret HOSTINGER_ENV_FILE."
echo "Next: git push origin main  →  Actions Deploy writes them to /opt/sweetcrust/backend_v2/.env.production"
