import { FastifyPluginAsync } from 'fastify'

const root: FastifyPluginAsync = async (fastify) => {
  fastify.get('/', async (_req, reply) => {
    reply.redirect('/docs')
  })
}

export default root
