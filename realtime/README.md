# SweetCrust Realtime (Fastify + Socket.IO)

Fan-out for order status, chat, delivery location, and presence.
Apps → nginx `/socket.io/` → realtime `:8081`. FastAPI services publish on Redis; this service emits to Socket.IO rooms.

## Run

```bash
cd backend_v2/realtime
cp .env.example .env   # JWT_SECRET_KEY must match FastAPI
npm install
npm run dev            # :8081
npm run build && npm start
```

Health: `GET /health`

## Auth

```js
io('https://api.example.com', { auth: { token: accessJwt } })
```

Access JWT (`type=access`) — HS256, `exp` checked, `jti` blacklist key `jwt:bl:{jti}` (same as Python).

Rooms joined on connect: `user:{id}`, plus role rooms `admin` / `retailers` / `delivery` / `rider:{id}`.

## Client events

| Event | Auth | Effect |
|-------|------|--------|
| `join_order` | yes | join `order:{id}` |
| `join_chat` | yes | join `chat:{id}` |
| `typing` | yes | peer typing indicator |
| `presence_ping` | yes | refresh presence → admin |
| `order_status` | admin/delivery | broadcast (optional; prefer REST→Redis) |

Chat/location **persist via REST**; realtime only broadcasts.

## Redis channels (`package/events/topics.py`)

| Channel | Emit |
|---------|------|
| `sc:order_status` | `order_status` → `order:{id}` + `admin` |
| `sc:chat_message` | `chat_message` → `chat:{id}` + `admin` (+ peer if sender admin/ai/system) |
| `sc:delivery_location` | `delivery_location` → `order:{id}` + `admin` |
| `sc:user_presence` | `user_presence` → `admin` |

## Docker

```bash
cd backend_v2
docker compose up -d --build realtime
curl http://127.0.0.1:8081/health
```
