#!/usr/bin/env bash
# Paste into Hostinger VPS browser console (root) when SSH port 22 is unreachable.
# Installs Docker, creates deploy dir. Then upload code via panel File Manager / SCP once SSH works.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Need root" >&2
  exit 1
fi

bash "$(dirname "$0")/setup-vps.sh"

# Ensure authorized_keys has the laptop key (idempotent)
mkdir -p /root/.ssh
chmod 700 /root/.ssh
PUB='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINeFmwDt2d3+/3CwKxpWeihNJW8ngCQ7cQNyqOqyWvgX ashoksahu8018183830@gmail.com'
grep -qF "$PUB" /root/.ssh/authorized_keys 2>/dev/null || echo "$PUB" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

# Open SSH if ufw was blocking
ufw allow OpenSSH || true
ufw allow 22/tcp || true
ufw --force enable || true

ss -lntp | grep -E ':22|:80' || true
echo "Bootstrap done. From laptop: cd backend_v2 && ./deploy/hostinger/deploy.sh"
