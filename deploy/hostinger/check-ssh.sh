#!/usr/bin/env bash
# Quick connectivity check before deploy.
set -euo pipefail
DEPLOY_HOST="${DEPLOY_HOST:-145.223.21.127}"
DEPLOY_USER="${DEPLOY_USER:-root}"
echo "Testing SSH ${DEPLOY_USER}@${DEPLOY_HOST}…"
ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new \
  "${DEPLOY_USER}@${DEPLOY_HOST}" 'uname -a; command -v docker || echo "docker: missing"'
echo "SSH OK"
