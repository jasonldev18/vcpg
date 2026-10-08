export const API_BASE = 'http://127.0.0.1:8000'
const TOKEN_HEADER = 'X-VCPG-Token'

let session: Promise<string> | undefined

// The per-launch token guards every state-changing route (SECURITY.md section 8).
function sessionToken(): Promise<string> {
  session ??= request<{ token: string }>('GET', '/api/session').then((s) => s.token)
  return session
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (method !== 'GET') headers[TOKEN_HEADER] = await sessionToken()
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
