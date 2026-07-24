/**
 * Socket.IO realtime — JWT auth + Redis fan-out from FastAPI services.
 * Channels must match package/events/topics.py.
 */
import './loadEnv.js'
import { createHmac } from 'node:crypto'
import Fastify from 'fastify'
import { Redis } from 'ioredis'
import { Server as SocketIOServer, type Socket } from 'socket.io'

const PORT = Number(process.env.PORT || 8081)
const REDIS_URL = process.env.REDIS_URL || ''
const JWT_SECRET = process.env.JWT_SECRET_KEY || process.env.JWT_SECRET || ''

const CHANNELS = {
  ORDER_STATUS: 'sc:order_status',
  CHAT_MESSAGE: 'sc:chat_message',
  DELIVERY_LOCATION: 'sc:delivery_location',
  USER_PRESENCE: 'sc:user_presence',
  ADMIN_EVENT: 'sc:admin_event',
  USER_EVENT: 'sc:user_event',
} as const

type AuthUser = { id: number; role?: string }

const app = Fastify({ logger: true })

let redisPub: Redis | null = null
let redisSub: Redis | null = null

if (REDIS_URL) {
  redisPub = new Redis(REDIS_URL, { maxRetriesPerRequest: null })
  redisSub = new Redis(REDIS_URL, { maxRetriesPerRequest: null })
  redisPub.on('error', (err) => app.log.warn({ err }, 'redis pub error'))
  redisSub.on('error', (err) => app.log.warn({ err }, 'redis sub error'))
}

app.get('/', async () => ({
  service: 'realtime',
  ok: true,
  hint: 'Socket.IO at /socket.io — Expo Metro must use another port (e.g. 8082), not 8081',
  health: '/health',
}))

app.get('/health', async () => {
  let redisOk = false
  if (redisPub) {
    try {
      redisOk = (await redisPub.ping()) === 'PONG'
    } catch {
      redisOk = false
    }
  }
  return {
    service: 'realtime',
    runtime: 'fastify',
    ok: true,
    redis: redisOk,
    jwt: Boolean(JWT_SECRET),
  }
})

await app.ready()

const io = new SocketIOServer(app.server, {
  cors: { origin: true, credentials: true },
  path: '/socket.io',
})

function b64urlJson(part: string): Record<string, unknown> | null {
  try {
    const pad = '='.repeat((4 - (part.length % 4)) % 4)
    const json = Buffer.from(part.replace(/-/g, '+').replace(/_/g, '/') + pad, 'base64').toString(
      'utf8'
    )
    return JSON.parse(json) as Record<string, unknown>
  } catch {
    return null
  }
}

async function isJtiBlacklisted(jti: unknown): Promise<boolean> {
  if (!jti || !redisPub) return false
  try {
    return (await redisPub.get(`jwt:bl:${String(jti)}`)) === '1'
  } catch {
    return false
  }
}

/** HS256 JWT verify — matches package.common.auth.jwt (python-jose). */
async function userFromToken(token: string | undefined): Promise<AuthUser | null> {
  if (!token || !JWT_SECRET) return null
  const parts = token.split('.')
  if (parts.length !== 3) return null
  const [h, p, s] = parts
  const data = `${h}.${p}`
  const sig = createHmac('sha256', JWT_SECRET).update(data).digest('base64url')
  if (sig !== s) return null
  const payload = b64urlJson(p)
  if (!payload || payload.type !== 'access' || payload.sub == null) return null
  if (typeof payload.exp === 'number' && payload.exp * 1000 <= Date.now()) return null
  if (await isJtiBlacklisted(payload.jti)) return null
  return { id: Number(payload.sub), role: String(payload.role || '') }
}

function requireUser(socket: Socket): AuthUser | null {
  return (socket.data.user as AuthUser | null) || null
}

async function publishPresence(user: AuthUser, online: boolean): Promise<void> {
  const payload = {
    user_id: user.id,
    online,
    role: user.role || null,
    at: new Date().toISOString(),
  }
  // Prefer Redis so multi-instance sockets stay in sync; local emit if Redis off.
  if (redisPub) {
    try {
      await redisPub.publish(CHANNELS.USER_PRESENCE, JSON.stringify(payload))
      return
    } catch (err) {
      app.log.debug({ err }, 'presence publish failed')
    }
  }
  io.to('admin').emit('user_presence', payload)
}

io.on('connection', (socket) => {
  void (async () => {
    const auth = socket.handshake.auth as { token?: string } | undefined
    const user = await userFromToken(auth?.token)
    socket.data.user = user

    if (user) {
      void socket.join(`user:${user.id}`)
      if (user.role === 'admin') void socket.join('admin')
      if (user.role === 'retailer') void socket.join('retailers')
      if (user.role === 'delivery') {
        void socket.join('delivery')
        void socket.join(`rider:${user.id}`)
      }
      await publishPresence(user, true)
    }

    app.log.info({ id: socket.id, userId: user?.id }, 'socket connected')
  })()

  socket.on('join_order', (data: { order_id?: string | number } | string | number) => {
    const u = requireUser(socket)
    if (!u) {
      socket.emit('error', { detail: 'Authentication required' })
      return
    }
    const orderId = typeof data === 'object' ? data?.order_id : data
    if (orderId == null) return
    const room = `order:${orderId}`
    void socket.join(room)
    socket.emit('joined', { room })
  })

  socket.on('join_chat', (data: { conversation_id?: string | number }) => {
    const u = requireUser(socket)
    if (!u) {
      socket.emit('error', { detail: 'Authentication required' })
      return
    }
    const id = data?.conversation_id
    if (id == null) return
    void socket.join(`chat:${id}`)
    socket.emit('joined', { room: `chat:${id}` })
  })

  socket.on('typing', (data: { conversation_id?: number; is_typing?: boolean }) => {
    const u = requireUser(socket)
    if (!u || data?.conversation_id == null) return
    socket.to(`chat:${data.conversation_id}`).emit('typing', {
      conversation_id: data.conversation_id,
      user_id: u.id,
      is_typing: data.is_typing ?? true,
    })
  })

  socket.on('presence_ping', () => {
    void (async () => {
      const u = requireUser(socket)
      if (!u) return
      await publishPresence(u, true)
      socket.emit('presence_pong', { ok: true, at: new Date().toISOString() })
    })()
  })

  socket.on('order_status', (data: { order_id?: number }) => {
    const u = requireUser(socket)
    if (!u || !['admin', 'delivery'].includes(u.role || '')) {
      socket.emit('error', { detail: 'Not allowed' })
      return
    }
    if (data?.order_id == null) return
    io.to(`order:${data.order_id}`).emit('order_status', data)
    io.to('admin').emit('order_status', data)
  })

  socket.on('disconnect', () => {
    const u = requireUser(socket)
    if (u) void publishPresence(u, false)
    app.log.info({ id: socket.id, userId: u?.id }, 'socket disconnected')
  })
})

async function startRedisFanout(): Promise<void> {
  if (!redisSub || !redisPub) {
    app.log.warn('REDIS_URL unset — socket fan-out from FastAPI disabled')
    return
  }
  await redisSub.subscribe(...Object.values(CHANNELS))
  redisSub.on('message', (channel: string, message: string) => {
    try {
      const data = JSON.parse(message) as Record<string, unknown>
      if (channel === CHANNELS.ORDER_STATUS && data.order_id != null) {
        io.to(`order:${data.order_id}`).emit('order_status', data)
        io.to('admin').emit('order_status', data)
        // Fan out to the assigned rider (rooms joined on connect for role=delivery)
        const riderUserId = data.rider_user_id ?? data.delivery_user_id
        if (riderUserId != null) {
          io.to(`rider:${riderUserId}`).emit('order_status', data)
          io.to(`user:${riderUserId}`).emit('order_status', data)
        }
        io.to('delivery').emit('order_status', data)
      }
      if (channel === CHANNELS.CHAT_MESSAGE && data.conversation_id != null) {
        io.to(`chat:${data.conversation_id}`).emit('chat_message', data)
        io.to('admin').emit('chat_message', data)
        const role = String(data.sender_role || '')
        if (data.peer_user_id != null && ['admin', 'ai', 'system'].includes(role)) {
          io.to(`user:${data.peer_user_id}`).emit('chat_message', data)
        }
      }
      if (channel === CHANNELS.DELIVERY_LOCATION && data.order_id != null) {
        io.to(`order:${data.order_id}`).emit('delivery_location', data)
        io.to('admin').emit('delivery_location', data)
      }
      if (channel === CHANNELS.USER_PRESENCE) {
        io.to('admin').emit('user_presence', data)
      }
      if (channel === CHANNELS.ADMIN_EVENT) {
        io.to('admin').emit('admin_event', data)
      }
      if (channel === CHANNELS.USER_EVENT && data.user_id != null) {
        io.to(`user:${data.user_id}`).emit('user_event', data)
      }
    } catch (e) {
      app.log.warn({ err: e }, 'bad redis message')
    }
  })
  app.log.info({ channels: Object.values(CHANNELS) }, 'redis subscribed')
}

async function shutdown(signal: string): Promise<void> {
  app.log.info({ signal }, 'shutting down realtime')
  try {
    io.close()
  } catch {
    /* ignore */
  }
  try {
    await redisSub?.quit()
  } catch {
    /* ignore */
  }
  try {
    await redisPub?.quit()
  } catch {
    /* ignore */
  }
  await app.close()
  process.exit(0)
}

process.on('SIGINT', () => void shutdown('SIGINT'))
process.on('SIGTERM', () => void shutdown('SIGTERM'))

await startRedisFanout()
await app.listen({ port: PORT, host: '0.0.0.0' })
app.log.info({ port: PORT }, 'realtime listening')
