# Routes

- `GET /` — service pointer
- `GET /gateway/health` — gateway probe (+ upstream URLs)
- Everything else under `/api/v1/*` is handled by the proxy plugin
