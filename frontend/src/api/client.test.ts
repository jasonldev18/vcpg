import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, API_BASE } from './client'

type Call = { url: string; method: string; headers: Record<string, string> }

function fakeServer() {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      const headers = init.headers as Record<string, string>
      calls.push({ url, method: init.method ?? 'GET', headers })
      const body = url.endsWith('/api/session') ? { token: 'launch-token' } : { ok: true }
      return new Response(JSON.stringify(body), { status: 200 })
    }),
  )
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('sends the session token on state-changing requests, fetched once', async () => {
    const calls = fakeServer()
    await api.post('/api/a', { x: 1 })
    await api.put('/api/b')
    const writes = calls.filter((c) => c.method !== 'GET')
    expect(writes.map((c) => c.headers['X-VCPG-Token'])).toEqual(['launch-token', 'launch-token'])
    expect(calls.filter((c) => c.url === `${API_BASE}/api/session`)).toHaveLength(1)
  })

  it('does not send the token on reads', async () => {
    const calls = fakeServer()
    await api.get('/api/health')
    expect(calls[0].headers['X-VCPG-Token']).toBeUndefined()
  })

  it('throws on an error status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{}', { status: 403 })),
    )
    await expect(api.get('/api/health')).rejects.toThrow('GET /api/health failed: 403')
  })
})
