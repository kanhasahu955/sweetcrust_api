# SweetCrust `backend_v2`

Microservices cut from the legacy monolith (`backend/` — do not modify).

```
backend_v2/
  package/                 # shared FastAPI infra
  services/                # domain FastAPI services (:8001–8027)
  gateway/                 Fastify HTTP proxy :8080  (= api-gateway)
  realtime/                Fastify Socket.IO + Redis :8081
  nginx/                   :80 → gateway + /socket.io → realtime
```

## Topology

```
apps → nginx:80 → gateway:8080 → FastAPI :8001–8027
              └→ realtime:8081
FastAPI → Redis publish → realtime → Socket.IO rooms
```

This stack is **independent of legacy `backend/`**. Credentials live only in **`backend_v2/.env`**:

- FastAPI / `package`: `package.common.env.ROOT_ENV` → `service_env_files()` / `package_env_files()`
- Docker Compose: `env_file: .env` (+ per-service `PORT` / `SERVICE_PORT`)
- Local: `./scripts/dev-service.sh <service> <port>` sources `backend_v2/.env`
- Fastify gateway + realtime: `src/loadEnv.ts` loads `backend_v2/.env`

Copy `.env.example` → `.env` to start. Use **uv** (not manual venv / not legacy `backend/`):

```bash
cd backend_v2
uv sync                 # shared deps
uv sync --extra ai      # + AI stack when needed
```

## Domain → port → features

| Domain | Port | Real features |
|--------|------|----------------|
| api-gateway | 8080 | HTTP proxy + request-id + CORS |
| auth | 8001 | OTP, JWT, Google, admin/retailer/delivery login |
| catalog | 8002 | Home, categories, products, favorites, reviews |
| cart | 8003 | Cart CRUD + items |
| payment | 8004 | Methods, Razorpay create/verify, confirm |
| rider | 8005 | Delivery check, rider me/orders/location/deliver |
| ai | 8006 | Chatbot, FAQs, voice, AI admin tools |
| store-ops | 8007 | Full admin BFF + retailer BFF + uploads |
| user | 8008 | `GET/PATCH /auth/me` |
| search | 8009 | `/customer/search`, suggest |
| assortment | 8010 | Admin range flags, available SKUs, retailer catalog |
| pricing | 8011 | Quote/bulk quote, admin price edit, cake estimate |
| promotion | 8012 | Apply coupon, validate, admin coupons CRUD |
| inventory | 8013 | Inventory, low-stock, movements, stock patch |
| picking | 8014 | Kitchen queue, start/pack, stats |
| checkout | 8015 | Place order |
| order | 8016 | Orders, cancel/reorder, invoice/rate/track, cakes, returns |
| invoice | 8017 | Customer invoice (also on order via gateway) |
| location | 8018 | Addresses + Google geo suggest/place/reverse/pincode |
| dispatch | 8019 | Live delivery map, assign/status helpers |
| tracking | 8020 | Public share track |
| routing | 8021 | Stops, optimize route, ETA, assign |
| notification | 8022 | List + mark read |
| support | 8023 | Customer chats + messages |
| rating | 8024 | Order rate + product reviews |
| analytics | 8025 | Dashboard + reports |
| forecast | 8026 | Demand, stockout risk, revenue, SKU forecast |
| commerce (residual) | 8027 | Wallet, referral, subscriptions, gift, corporate, profile |

See `SERVICE_PORTS.md` for the full port list. Legacy folders `admin_service`, `payments_service`, `delivery_service` remain as copies of `store_ops` / `payment` / `rider` — prefer the new names.

## Internal layout (each FastAPI service)

```
services/<name>_service/
  main.py
  app/
    routes/         # HTTP paths → controllers
    controllers/    # thin adapters (request shaping)
    services/       # business / use-case logic
    repositories/   # SQLModel data access
    models/ schemas/ config/
    producers/ consumers/
    deps.py check.py
```

Every active service has real code in `services/`, `controllers/`, and `repositories/` — not empty scaffold folders. Middleware, errors, JWT, DB pool, redis stay in `package/`.

## Run everything locally (no Docker)

Prereqs once: `uv`, Node/npm, Redis (`brew install redis && brew services start redis`).

```bash
cd backend_v2
make up
# same as: ./scripts/dev-all.sh
```

Starts host Redis, all FastAPI services (`uv`), gateway `:8080`, realtime `:8081`. Logs → `logs/`. Ctrl+C stops all.

```bash
make up-no-ai   # skip AI service
make redis      # start local redis-server only
```

## Run one service

```bash
cd backend_v2
uv sync
./scripts/dev-service.sh auth_service 8001
./scripts/uv-check.sh auth_service
```

## Docker (full stack + nginx :80)

```bash
cd backend_v2
docker compose up -d --build
# or: make up-docker
curl http://127.0.0.1/gateway/health
curl http://127.0.0.1:8081/health
```

## Production (Hostinger VPS)

Target: `https://api.bakerywala.cloud` on VPS `145.223.21.127`.

```bash
cd backend_v2
cp .env.production.example .env.production   # fill secrets
./deploy/hostinger/deploy.sh                 # rsync + compose up
# on server after HTTP is healthy:
./deploy/hostinger/issue-cert.sh
```

Hostinger + GitHub CI/CD deploy **this backend only** (not admin/mobile). See [`deploy/hostinger/GITHUB_ACTIONS.md`](deploy/hostinger/GITHUB_ACTIONS.md). Makefile: `prod-deploy`, `prod-up`, `prod-down`, `prod-logs`, `prod-health`, `prod-cert`.

## Package

```bash
cd backend_v2
uv run python -m package.check_package
```
