import { vi } from 'vitest'
import { API_BASE } from './api/client'
import type { Project, Step } from './api/types'

export interface Call {
  method: string
  path: string
  body: unknown
}

type Reply = unknown | ((body: unknown) => unknown)

// Routes "METHOD /path" to canned JSON (or a Response) and records every request.
export function fakeApi(routes: Record<string, Reply>): Call[] {
  const calls: Call[] = []
  const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? 'GET'
      const path = url.replace(API_BASE, '')
      const body = init.body ? JSON.parse(init.body as string) : undefined
      if (path === '/api/session') return json({ token: 'test-token' })
      calls.push({ method, path, body })
      const key = `${method} ${path}`
      if (!(key in routes)) return json({ detail: `no fake for ${key}` }, 404)
      const reply = routes[key]
      const out = typeof reply === 'function' ? reply(body) : reply
      return out instanceof Response ? out : json(out)
    }),
  )
  return calls
}

export function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: 1,
    project_id: 1,
    position: 0,
    title: 'KNN recommender core',
    component: 'backend',
    goal: 'Recommend five films.',
    concepts: ['cosine similarity'],
    state: 'planned',
    current: true,
    lesson: null,
    build_note: null,
    review_note: null,
    build: { running: false, paused: false, error: null, isolation: 'venv' },
    chat: [],
    gate: [],
    progress: { covered: 0, total: 4 },
    can_hint: false,
    ...overrides,
  }
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 1,
    name: 'Movie Recommender',
    brief: 'recommend movies',
    status: 'active',
    plan: null,
    steps: [makeStep()],
    current_step_id: 1,
    ...overrides,
  }
}
