# SweetCrust Admin Service

Admin dashboard + temporary retailer BFF (non-AI).

Uses shared `backend_v2/package/` for: `create_service_app` (middleware + errors),
`service_lifespan` (logging boot), `get_logger`, `AppError` family, `ok`/`HealthOut`,
`utc_now`/`day_bounds`, auth guards, DB sessions, redis publish/rate-limit.

## Run

```bash
cd backend_v2
export PYTHONPATH="$PWD:$PWD/services/admin_service"
./scripts/dev-service.sh admin_service 8007
./scripts/uv-check.sh admin_service
```

## Gateway

- `/api/v1/admin/*` (except AI paths) → this service `:8007`
- `/api/v1/admin/products/ai-upload/publish` → here
- AI analyze / chatbot / insights → `ai_service`
- `/api/v1/retailer/*` (non-AI) → here

## Scope (P0)

Dashboard, shops approve/create, products/categories/stock, AI publish, orders status/assign,
delivery persons/live, coupons, banners, tickets, settings, chats (human), returns (admin),
uploads (local), retailer me/catalog/orders.

## Layout

`app/{config,routes,controllers,services,repositories,producers,consumers,models,schemas}`
