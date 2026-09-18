import test from 'node:test'
import assert from 'node:assert/strict'
import api, { getPendingRequestCount, cancelPendingReads } from '../src/api/index.js'

const storage = new Map()
globalThis.localStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: key => storage.delete(key)
}
globalThis.window = { location: { pathname: '/login', href: '' } }
const response = (config, value) => ({ config, data: value, status: 200, statusText: 'OK', headers: {} })

test('fresh server response is not replaced by stale GET data', async () => {
  localStorage.setItem('token', 'session-a')
  let value = 1
  const adapter = async config => response(config, value++)
  assert.equal((await api.get('/test', { adapter })).data, 1)
  assert.equal((await api.get('/test', { adapter })).data, 2)
  assert.equal(getPendingRequestCount(), 0)
})

test('old in-flight response cannot populate a new session', async () => {
  localStorage.setItem('token', 'session-a')
  const adapter = async config => {
    localStorage.setItem('token', 'session-b')
    return response(config, 'private-a')
  }
  await assert.rejects(api.get('/test', { adapter }), { code: 'ERR_CANCELED' })
  assert.equal(getPendingRequestCount(), 0)
})

test('identical POSTs do not cancel each other', async () => {
  const adapter = async config => {
    await new Promise(resolve => setTimeout(resolve, 10))
    assert.equal(config.signal.aborted, false)
    return response(config, 'saved')
  }
  const results = await Promise.all([api.post('/submit', { answer: 1 }, { adapter }), api.post('/submit', { answer: 1 }, { adapter })])
  assert.equal(results.length, 2)
  assert.equal(getPendingRequestCount(), 0)
})

test('401 from old session does not sign out the new account', async () => {
  localStorage.setItem('token', 'session-a')
  const adapter = async config => {
    localStorage.setItem('token', 'session-b')
    throw Object.assign(new Error('expired'), { config, response: { status: 401 } })
  }
  await assert.rejects(api.get('/test', { adapter }))
  assert.equal(localStorage.getItem('token'), 'session-b')
})

test('navigation only cancels reads, not a saving submission', async () => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  const seen = []
  const adapter = async config => {
    seen.push(config)
    await gate
    return response(config, 'done')
  }
  const read = api.get('/pending', { adapter }).catch(error => error)
  const write = api.post('/saving', {}, { adapter })
  await new Promise(resolve => setImmediate(resolve))
  cancelPendingReads()
  assert.equal(seen.find(config => config.method === 'get').signal.aborted, true)
  assert.equal(seen.find(config => config.method === 'post').signal.aborted, false)
  release()
  assert.equal((await read).code, 'ERR_CANCELED')
  assert.equal((await write).data, 'done')
  assert.equal(getPendingRequestCount(), 0)
})
