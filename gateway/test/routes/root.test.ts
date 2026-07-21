import { test } from 'node:test'
import * as assert from 'node:assert'
import { build } from '../helper'

test('root route', async (t) => {
  const app = await build(t)
  const res = await app.inject({ url: '/' })
  const body = JSON.parse(res.payload)
  assert.equal(body.service, 'gateway')
  assert.equal(body.health, '/gateway/health')
})

test('gateway health', async (t) => {
  const app = await build(t)
  const res = await app.inject({ url: '/gateway/health' })
  assert.equal(res.statusCode, 200)
  const body = JSON.parse(res.payload)
  assert.equal(body.ok, true)
  assert.ok(body.upstreams?.admin)
  assert.ok(res.headers['x-request-id'])
})
