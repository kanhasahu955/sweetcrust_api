#!/usr/bin/env bash
# One-time (or refresh): generate secrets and push them to GitHub Actions.
# Requires: gh auth login, openssl
#
#   ./deploy/hostinger/bootstrap-github-secrets.sh
#   ./deploy/hostinger/bootstrap-github-secrets.sh --email you@example.com
#   ./deploy/hostinger/bootstrap-github-secrets.sh --force   # rotate MYSQL/JWT
#
# After this, every `git push origin main` builds .env.production from these secrets
# and deploys to the VPS (see .github/workflows/deploy.yml).
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-kanhasahu955/sweetcrust_api}"
EMAIL=""
FORCE=0
SSH_KEY_FILE="${HOSTINGER_SSH_KEY_FILE:-$HOME/.ssh/hostinger_gha}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --email=*) EMAIL="${1#*=}"; shift ;;
    --email) EMAIL="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--email you@domain.com] [--force]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! command -v gh >/dev/null; then
  echo "Install GitHub CLI: brew install gh && gh auth login" >&2
  exit 1
fi
if ! command -v openssl >/dev/null; then
  echo "openssl required" >&2
  exit 1
fi

gh auth status >/dev/null

rand() { openssl rand -base64 32 | tr -d '/+=' | head -c 40; }

set_secret() {
  local name="$1" value="$2"
  printf '%s' "$value" | gh secret set "$name" --repo "$REPO"
  echo "set $name"
}

has_secret() {
  gh secret list --repo "$REPO" 2>/dev/null | awk '{print $1}' | grep -qx "$1"
}

echo "Repo: $REPO"

# --- Hostinger connection (stable defaults) ---
set_secret HOSTINGER_HOST "${HOSTINGER_HOST:-145.223.21.127}"
set_secret HOSTINGER_USER "${HOSTINGER_USER:-root}"

if [[ -f "$SSH_KEY_FILE" ]]; then
  gh secret set HOSTINGER_SSH_KEY --repo "$REPO" <"$SSH_KEY_FILE"
  echo "set HOSTINGER_SSH_KEY from $SSH_KEY_FILE"
else
  echo "WARNING: missing $SSH_KEY_FILE — set HOSTINGER_SSH_KEY manually in GitHub if deploy fails SSH." >&2
fi

# --- App secrets (generate once; --force rotates) ---
if [[ "$FORCE" -eq 1 ]] || ! has_secret MYSQL_ROOT_PASSWORD; then
  set_secret MYSQL_ROOT_PASSWORD "$(rand)"
else
  echo "keep MYSQL_ROOT_PASSWORD (use --force to rotate)"
fi

if [[ "$FORCE" -eq 1 ]] || ! has_secret MYSQL_PASSWORD; then
  set_secret MYSQL_PASSWORD "$(rand)"
else
  echo "keep MYSQL_PASSWORD (use --force to rotate)"
fi

if [[ "$FORCE" -eq 1 ]] || ! has_secret JWT_SECRET_KEY; then
  set_secret JWT_SECRET_KEY "$(rand)$(rand)"
else
  echo "keep JWT_SECRET_KEY (use --force to rotate)"
fi

if [[ -n "$EMAIL" ]]; then
  set_secret CERTBOT_EMAIL "$EMAIL"
elif ! has_secret CERTBOT_EMAIL; then
  echo "CERTBOT_EMAIL not set. Re-run: $0 --email you@example.com" >&2
  exit 1
else
  echo "keep CERTBOT_EMAIL"
fi

echo
echo "Done. Secrets on GitHub:"
gh secret list --repo "$REPO"
echo
echo "Next: git push origin main  →  Actions Deploy builds .env.production and deploys to VPS."
echo "Optional API keys (manual): GROQ_API_KEY, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, …"
