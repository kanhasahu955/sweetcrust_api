import { randomUUID } from 'node:crypto'
import fp from 'fastify-plugin'
import proxy from '@fastify/http-proxy'
import cors from '@fastify/cors'

/**
 * Path → FastAPI microservice. Most-specific prefixes first.
 * AI admin/retailer paths are registered before catch-alls.
 *
 * Invoice/rate/track under `/customer/orders/{id}/…` are served by order-service
 * (http-proxy cannot split path-param suffixes to sibling services).
 */
export default fp(async (fastify) => {
  fastify.addHook('onRequest', async (request, reply) => {
    const incoming = request.headers['x-request-id']
    const id = typeof incoming === 'string' && incoming.trim() ? incoming.trim() : randomUUID()
    request.headers['x-request-id'] = id
    reply.header('x-request-id', id)
  })

  await fastify.register(cors, {
    origin: true,
    credentials: true,
  })

  const auth = process.env.AUTH_URL || 'http://127.0.0.1:8001'
  const catalog = process.env.CATALOG_URL || 'http://127.0.0.1:8002'
  const cart = process.env.CART_URL || 'http://127.0.0.1:8003'
  const payment = process.env.PAYMENT_URL || process.env.PAYMENTS_URL || 'http://127.0.0.1:8004'
  const rider = process.env.RIDER_URL || process.env.DELIVERY_URL || 'http://127.0.0.1:8005'
  const ai = process.env.AI_URL || 'http://127.0.0.1:8006'
  const storeOps = process.env.STORE_OPS_URL || process.env.ADMIN_URL || 'http://127.0.0.1:8007'
  const user = process.env.USER_URL || 'http://127.0.0.1:8008'
  const search = process.env.SEARCH_URL || 'http://127.0.0.1:8009'
  const assortment = process.env.ASSORTMENT_URL || 'http://127.0.0.1:8010'
  const pricing = process.env.PRICING_URL || 'http://127.0.0.1:8011'
  const promotion = process.env.PROMOTION_URL || 'http://127.0.0.1:8012'
  const inventory = process.env.INVENTORY_URL || 'http://127.0.0.1:8013'
  const picking = process.env.PICKING_URL || 'http://127.0.0.1:8014'
  const checkout = process.env.CHECKOUT_URL || 'http://127.0.0.1:8015'
  const order = process.env.ORDER_URL || 'http://127.0.0.1:8016'
  const location = process.env.LOCATION_URL || 'http://127.0.0.1:8018'
  const dispatch = process.env.DISPATCH_URL || 'http://127.0.0.1:8019'
  const tracking = process.env.TRACKING_URL || 'http://127.0.0.1:8020'
  const routing = process.env.ROUTING_URL || 'http://127.0.0.1:8021'
  const notification = process.env.NOTIFICATION_URL || 'http://127.0.0.1:8022'
  const support = process.env.SUPPORT_URL || 'http://127.0.0.1:8023'
  const rating = process.env.RATING_URL || 'http://127.0.0.1:8024'
  const analytics = process.env.ANALYTICS_URL || 'http://127.0.0.1:8025'
  const forecast = process.env.FORECAST_URL || 'http://127.0.0.1:8026'
  const commerce = process.env.COMMERCE_URL || 'http://127.0.0.1:8027'

  const upstreams = {
    auth,
    catalog,
    cart,
    payment,
    rider,
    ai,
    storeOps,
    user,
    search,
    assortment,
    pricing,
    promotion,
    inventory,
    picking,
    checkout,
    order,
    location,
    dispatch,
    tracking,
    routing,
    notification,
    support,
    rating,
    analytics,
    forecast,
    commerce,
  }
  fastify.decorate('upstreams', upstreams)

  const routes: { prefix: string; upstream: string }[] = [
    { prefix: '/api/v1/auth/me', upstream: user },
    { prefix: '/api/v1/auth', upstream: auth },
    { prefix: '/api/v1/payments', upstream: payment },
    { prefix: '/api/v1/delivery', upstream: rider },

    { prefix: '/api/v1/ai', upstream: ai },
    { prefix: '/api/v1/voice', upstream: ai },
    { prefix: '/api/v1/customer/ai', upstream: ai },
    { prefix: '/api/v1/customer/calls', upstream: ai },
    { prefix: '/api/v1/customer/faqs', upstream: ai },
    { prefix: '/api/v1/admin/calls/ai-outbound', upstream: ai },
    { prefix: '/api/v1/admin/products/ai-upload/publish', upstream: storeOps },
    { prefix: '/api/v1/admin/products/ai-upload', upstream: ai },
    { prefix: '/api/v1/admin/categories/ai-image', upstream: ai },
    { prefix: '/api/v1/admin/coupons/ai-suggest', upstream: ai },
    { prefix: '/api/v1/admin/chatbot', upstream: ai },
    { prefix: '/api/v1/admin/insights', upstream: ai },
    { prefix: '/api/v1/admin/returns/ai-assess', upstream: ai },
    { prefix: '/api/v1/retailer/ai', upstream: ai },
    { prefix: '/api/v1/retailer/products/ai-suggest', upstream: ai },

    // Domain admin slices (before /admin catch-all)
    { prefix: '/api/v1/admin/assortment', upstream: assortment },
    { prefix: '/api/v1/admin/pricing', upstream: pricing },
    { prefix: '/api/v1/admin/picking', upstream: picking },
    { prefix: '/api/v1/admin/routing', upstream: routing },
    { prefix: '/api/v1/admin/forecast', upstream: forecast },
    { prefix: '/api/v1/admin/coupons', upstream: promotion },
    { prefix: '/api/v1/admin/inventory', upstream: inventory },
    { prefix: '/api/v1/admin/dashboard', upstream: analytics },
    { prefix: '/api/v1/admin/reports', upstream: analytics },
    { prefix: '/api/v1/admin/delivery/live', upstream: dispatch },

    { prefix: '/api/v1/pricing', upstream: pricing },
    { prefix: '/api/v1/assortment', upstream: assortment },
    { prefix: '/api/v1/picking', upstream: picking },
    { prefix: '/api/v1/routing', upstream: routing },
    { prefix: '/api/v1/forecast', upstream: forecast },

    { prefix: '/api/v1/retailer/assortment', upstream: assortment },
    { prefix: '/api/v1/admin', upstream: storeOps },
    { prefix: '/api/v1/retailer', upstream: storeOps },
    { prefix: '/api/v1/uploads', upstream: storeOps },
    { prefix: '/api/v1/geo', upstream: location },

    { prefix: '/api/v1/customer/search', upstream: search },
    { prefix: '/api/v1/customer/products', upstream: catalog },
    { prefix: '/api/v1/customer/categories', upstream: catalog },
    { prefix: '/api/v1/customer/brands', upstream: catalog },
    { prefix: '/api/v1/customer/shops', upstream: catalog },
    { prefix: '/api/v1/customer/settings', upstream: catalog },
    { prefix: '/api/v1/customer/home', upstream: catalog },
    { prefix: '/api/v1/customer/payments', upstream: payment },
    { prefix: '/api/v1/customer/delivery', upstream: rider },
    { prefix: '/api/v1/customer/coupons', upstream: promotion },
    { prefix: '/api/v1/customer/cart/coupon', upstream: promotion },
    { prefix: '/api/v1/customer/cart', upstream: cart },
    { prefix: '/api/v1/customer/checkout', upstream: checkout },
    { prefix: '/api/v1/customer/orders', upstream: order },
    { prefix: '/api/v1/customer/custom-cakes', upstream: order },
    { prefix: '/api/v1/customer/returns', upstream: order },
    { prefix: '/api/v1/customer/notifications', upstream: notification },
    { prefix: '/api/v1/customer/chats', upstream: support },
    { prefix: '/api/v1/customer/addresses', upstream: location },
    { prefix: '/api/v1/customer/track', upstream: tracking },
    { prefix: '/api/v1/customer', upstream: commerce },

    { prefix: '/api/v1', upstream: storeOps },
    // /docs is the gateway portal (routes/docs.ts) — not proxied to store-ops
    { prefix: '/seed', upstream: storeOps },
    { prefix: '/uploads', upstream: storeOps },
    { prefix: '/health', upstream: storeOps },
  ]

  for (const r of routes) {
    await fastify.register(proxy, {
      upstream: r.upstream,
      prefix: r.prefix,
      rewritePrefix: r.prefix,
      http2: false,
      undici: {
        headersTimeout: 60_000,
        bodyTimeout: 120_000,
      },
      replyOptions: {
        rewriteRequestHeaders: (req, headers) => {
          const rid = req.headers['x-request-id']
          if (typeof rid === 'string' && rid) {
            headers['x-request-id'] = rid
          }
          return headers
        },
      },
    })
  }

  fastify.log.info(upstreams, 'gateway proxy upstreams')
})

declare module 'fastify' {
  interface FastifyInstance {
    upstreams: Record<string, string>
  }
}
