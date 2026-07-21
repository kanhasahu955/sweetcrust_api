# SweetCrust backend_v2 — local stack without Docker + Hostinger prod helpers
.PHONY: up up-no-ai sync check redis up-docker prod-up prod-down prod-logs prod-health prod-deploy prod-cert

up:
	./scripts/dev-all.sh

up-no-ai:
	./scripts/dev-all.sh --no-ai

# Local Redis only (Homebrew) — no Docker
redis:
	@command -v redis-server >/dev/null || (echo "brew install redis"; exit 1)
	redis-cli -h 127.0.0.1 ping 2>/dev/null | grep -q PONG \
		|| redis-server --daemonize yes --port 6379 --bind 127.0.0.1
	@redis-cli -h 127.0.0.1 ping

sync:
	uv sync --extra ai

check:
	./scripts/uv-check.sh auth_service

up-docker:
	docker compose up -d --build

# --- Production (Hostinger VPS) ---
# Requires .env.production (from .env.production.example)
prod-up:
	./deploy/hostinger/deploy.sh --local

prod-down:
	docker compose -f docker-compose.prod.yml --env-file .env.production down

prod-logs:
	docker compose -f docker-compose.prod.yml --env-file .env.production logs -f --tail=100

prod-health:
	@curl -fsS http://127.0.0.1/gateway/health && echo
	@curl -fsS https://api.bakerywala.cloud/gateway/health && echo || true

prod-deploy:
	./deploy/hostinger/deploy.sh

prod-cert:
	./deploy/hostinger/issue-cert.sh

# Generate MYSQL/JWT/CERTBOT (+ Hostinger SSH) secrets into GitHub via `gh`
secrets-bootstrap:
	./deploy/hostinger/bootstrap-github-secrets.sh --email "$(CERTBOT_EMAIL)"

# Upload entire local .env → GitHub secret HOSTINGER_ENV_FILE (used by Deploy)
secrets-sync-env:
	./deploy/hostinger/sync-env-to-github.sh --email "$(CERTBOT_EMAIL)"
