# AI service (`:8006`)

Thin `main.py` + `app/` (chatbot, RAG FAQs, Twilio voice, vision suggest, insights).

## Run

```bash
cd backend_v2
cp services/ai_service/.env.example services/ai_service/.env
export PYTHONPATH="$PWD:$PWD/services/ai_service"
./scripts/dev-service.sh ai_service 8006
```

## Checks

```bash
PYTHONPATH="$PWD:$PWD/services/ai_service" python3 -m app.check
curl -s localhost:8006/health | jq .
curl -s localhost:8006/api/v1/ai/status | jq .
```

## Gateway prefixes → this service

- `/api/v1/ai`, `/api/v1/voice`
- `/api/v1/customer/ai`, `/api/v1/customer/calls`, `/api/v1/customer/faqs`
- `/api/v1/admin/calls/ai-outbound`, `/admin/products/ai-upload`, `/admin/chatbot`
- `/api/v1/admin/insights`, `/api/v1/admin/returns/ai-assess`
- `/api/v1/admin/categories/ai-image`, `/admin/coupons/ai-suggest` (stub responses)
- `/api/v1/retailer/ai`, `/retailer/products/ai-suggest`

## Twilio

Set `TWILIO_*` and `TWILIO_WEBHOOK_BASE_URL` to the public gateway URL.  
Webhooks validate `X-Twilio-Signature` (skipped in dev if auth token unset).

## Notes

- Chat enforces conversation ownership + loads last turns as LLM history.
- Redis rate-limits chat (`AI_CHAT_RATE_LIMIT` / hour).
- RAG defaults to BM25; Pinecone is reported only when fully configured.

## Layout

`app/{config,routes,controllers,services,repositories,producers,consumers,models,schemas}`
