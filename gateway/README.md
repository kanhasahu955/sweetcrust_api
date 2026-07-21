# SweetCrust Gateway (Fastify)

HTTP reverse proxy: apps → nginx `:80` → gateway `:8080` → FastAPI services.

## Run

```bash
cd backend_v2/gateway
cp .env.example .env   # optional; defaults to 127.0.0.1:8001–8007
npm install
npm run dev            # :8080
# or
npm start
```

Probe: `GET /gateway/health` (not `/health` — that proxies to admin).

## Upstream map (summary)

| Prefix | Service |
|--------|---------|
| `/api/v1/auth` | auth `:8001` |
| catalog paths (`/customer/products`, `/geo`, …) | catalog `:8002` |
| commerce cart/orders/checkout | commerce `:8003` |
| payments | payments `:8004` |
| delivery | delivery `:8005` |
| AI + Twilio voice + AI admin paths | ai `:8006` |
| admin / retailer BFF / uploads / docs | admin `:8007` |

AI-specific admin routes are registered **before** the `/api/v1/admin` catch-all.
Publish path `/admin/products/ai-upload/publish` stays on admin.

## Docker

```bash
cd backend_v2
docker compose up -d --build gateway
curl http://127.0.0.1:8080/gateway/health
```
