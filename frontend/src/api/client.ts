export const API_BASE = 'http://127.0.0.1:8000'
const TOKEN_HEADER = 'X-VCPG-Token'

let session: Promise<string> | undefined

// The per-launch token guards every state-changing route (SECURITY.md section 8).
function sessionToken(): Promise<string> {
  session ??= request<{ token: string }>('GET', '/api/session').then((s) => s.token)
  return session
}

// The API reports problems as {detail}; show that to the user when it is there.
async function errorDetail(res: Response, fallback: string): Promise<string> {
  const body: unknown = await res.json().catch(() => null)
  const detail = (body as { detail?: unknown } | null)?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const raw = body instanceof Blob // file uploads go as the raw request body
  const headers: Record<string, string> = {
    'Content-Type': raw ? 'application/octet-stream' : 'application/json',
  }
  if (method !== 'GET') headers[TOKEN_HEADER] = await sessionToken()
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: raw ? body : body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await errorDetail(res, `${method} ${path} failed: ${res.status}`))
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  upload: <T>(path: string, file: Blob) => request<T>('POST', path, file),
}
