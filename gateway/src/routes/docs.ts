import { FastifyPluginAsync } from 'fastify'

/** Every FastAPI service + how the gateway routes its API prefixes. */
const SERVICES: {
  name: string
  port: number
  prefixes: string[]
}[] = [
  { name: 'auth', port: 8001, prefixes: ['/api/v1/auth'] },
  { name: 'catalog', port: 8002, prefixes: ['/api/v1/customer/home', '/api/v1/customer/products', '/api/v1/customer/categories', '/api/v1/customer/brands'] },
  { name: 'cart', port: 8003, prefixes: ['/api/v1/customer/cart'] },
  { name: 'payment', port: 8004, prefixes: ['/api/v1/payments', '/api/v1/customer/payments'] },
  { name: 'rider', port: 8005, prefixes: ['/api/v1/delivery', '/api/v1/customer/delivery'] },
  { name: 'ai', port: 8006, prefixes: ['/api/v1/ai', '/api/v1/customer/ai', '/api/v1/admin/chatbot', '/api/v1/retailer/ai'] },
  { name: 'store-ops', port: 8007, prefixes: ['/api/v1/admin', '/api/v1/retailer', '/api/v1/uploads'] },
  { name: 'user', port: 8008, prefixes: ['/api/v1/auth/me'] },
  { name: 'search', port: 8009, prefixes: ['/api/v1/customer/search'] },
  { name: 'assortment', port: 8010, prefixes: ['/api/v1/admin/assortment', '/api/v1/retailer/assortment'] },
  { name: 'pricing', port: 8011, prefixes: ['/api/v1/pricing', '/api/v1/admin/pricing'] },
  { name: 'promotion', port: 8012, prefixes: ['/api/v1/customer/coupons', '/api/v1/admin/coupons'] },
  { name: 'inventory', port: 8013, prefixes: ['/api/v1/admin/inventory'] },
  { name: 'picking', port: 8014, prefixes: ['/api/v1/admin/picking', '/api/v1/picking'] },
  { name: 'checkout', port: 8015, prefixes: ['/api/v1/customer/checkout'] },
  { name: 'order', port: 8016, prefixes: ['/api/v1/customer/orders', '/api/v1/customer/custom-cakes', '/api/v1/customer/returns'] },
  { name: 'invoice', port: 8017, prefixes: ['(via order paths on gateway)'] },
  { name: 'location', port: 8018, prefixes: ['/api/v1/geo', '/api/v1/customer/addresses'] },
  { name: 'dispatch', port: 8019, prefixes: ['/api/v1/admin/delivery/live'] },
  { name: 'tracking', port: 8020, prefixes: ['/api/v1/customer/track'] },
  { name: 'routing', port: 8021, prefixes: ['/api/v1/admin/routing', '/api/v1/routing'] },
  { name: 'notification', port: 8022, prefixes: ['/api/v1/customer/notifications'] },
  { name: 'support', port: 8023, prefixes: ['/api/v1/customer/chats'] },
  { name: 'rating', port: 8024, prefixes: ['(order rate / reviews)'] },
  { name: 'analytics', port: 8025, prefixes: ['/api/v1/admin/dashboard', '/api/v1/admin/reports'] },
  { name: 'forecast', port: 8026, prefixes: ['/api/v1/admin/forecast'] },
  { name: 'commerce', port: 8027, prefixes: ['/api/v1/customer (wallet/referral residual)'] },
]

function portalHtml(): string {
  const rows = SERVICES.map((s) => {
    const docs = `http://127.0.0.1:${s.port}/docs`
    const health = `http://127.0.0.1:${s.port}/health`
    const prefixes = s.prefixes.map((p) => `<code>${p}</code>`).join('<br>')
    return `<tr>
      <td><strong>${s.name}</strong></td>
      <td>:${s.port}</td>
      <td>${prefixes}</td>
      <td><a href="${docs}" target="_blank" rel="noreferrer">OpenAPI /docs</a></td>
      <td><a href="${health}" target="_blank" rel="noreferrer">/health</a></td>
    </tr>`
  }).join('\n')

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SweetCrust API — all services</title>
  <style>
    :root { color-scheme: light; font-family: ui-sans-serif, system-ui, sans-serif; }
    body { margin: 0; padding: 2rem; background: #f6f3ee; color: #1c1917; }
    h1 { font-size: 1.5rem; margin: 0 0 0.35rem; }
    p { color: #57534e; margin: 0 0 1.25rem; max-width: 52rem; line-height: 1.45; }
    .note { background: #fff; border: 1px solid #e7e5e4; padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 1.25rem; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e7e5e4; border-radius: 8px; overflow: hidden; }
    th, td { text-align: left; padding: 0.65rem 0.75rem; border-bottom: 1px solid #f5f5f4; vertical-align: top; font-size: 0.92rem; }
    th { background: #1c1917; color: #fafaf9; font-weight: 600; }
    tr:last-child td { border-bottom: 0; }
    code { font-size: 0.8rem; background: #f5f5f4; padding: 0.1rem 0.35rem; border-radius: 4px; }
    a { color: #0f766e; }
    .meta a { margin-right: 1rem; }
  </style>
</head>
<body>
  <h1>SweetCrust gateway — all microservices</h1>
  <p>
    The gateway (<code>:8080</code>) is a Fastify proxy. It does not own one combined Swagger UI.
    Call APIs through <code>http://127.0.0.1:8080/api/v1/…</code>; open each service’s docs below for schemas.
  </p>
  <div class="note meta">
    <a href="/gateway/health">Gateway health</a>
    <a href="/services">Services JSON</a>
    <a href="http://127.0.0.1:8007/docs">store-ops Swagger (admin/retailer)</a>
  </div>
  <table>
    <thead>
      <tr><th>Service</th><th>Port</th><th>Gateway prefixes</th><th>Docs</th><th>Health</th></tr>
    </thead>
    <tbody>
      ${rows}
    </tbody>
  </table>
</body>
</html>`
}

const docs: FastifyPluginAsync = async (fastify) => {
  fastify.get('/docs', async (_req, reply) => {
    reply.type('text/html').send(portalHtml())
  })

  fastify.get('/redoc', async (_req, reply) => {
    reply.redirect('/docs')
  })

  fastify.get('/openapi.json', async () => ({
    openapi: '3.0.3',
    info: {
      title: 'SweetCrust Gateway',
      description:
        'Proxy only — see /docs for per-service OpenAPI links. Upstream map is under /services.',
      version: '1.0.0',
    },
    paths: {},
    'x-services': SERVICES,
  }))

  fastify.get('/services', async () => ({
    gateway: 'http://127.0.0.1:8080',
    note: 'Hit APIs on the gateway; open each service /docs for schemas.',
    services: SERVICES.map((s) => ({
      name: s.name,
      port: s.port,
      docs: `http://127.0.0.1:${s.port}/docs`,
      health: `http://127.0.0.1:${s.port}/health`,
      openapi: `http://127.0.0.1:${s.port}/openapi.json`,
      gateway_prefixes: s.prefixes,
    })),
  }))
}

export default docs
