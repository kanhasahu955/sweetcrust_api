import { FastifyPluginAsync } from 'fastify'

/** Gateway probe — do not use /health (proxied to admin). */
const health: FastifyPluginAsync = async (fastify) => {
  fastify.get('/gateway/health', async () => ({
    service: 'gateway',
    runtime: 'fastify',
    ok: true,
    upstreams: fastify.upstreams,
  }))
}

export default health
