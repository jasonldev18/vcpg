import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { KeyStatus } from '../api/types'
import { useAction } from './useAction'

const PATH = '/api/core/anthropic'

export function CoreAccess({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<KeyStatus | null>(null)
  const [key, setKey] = useState('')
  const [note, setNote] = useState<string | null>(null)
  const { busy, error, run } = useAction()

  useEffect(() => {
    void api.get<KeyStatus>(PATH).then(setStatus)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])

  const act = async (action: () => Promise<KeyStatus>, done: string) => {
    const s = await run(action)
    if (s) {
      setStatus(s)
      setKey('')
      setNote(done)
    }
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Core access">
      <section className="panel stack core-access">
        <header className="row spread">
          <h1>Core access</h1>
          <button onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <h2>
          <span className={`light ${status?.saved ? 'on' : 'off'}`} aria-hidden="true" />
          Anthropic API key
        </h2>
        <p className="mute">
          {status === null
            ? 'Checking…'
            : status.saved
              ? `Saved in your OS keychain, ending in ${status.last4}.`
              : 'No key saved.'}
        </p>
        <input
          type="password"
          autoComplete="off"
          aria-label="Paste a new Anthropic API key"
          placeholder="sk-ant-…"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <div className="row">
          <button
            className="primary"
            disabled={busy || key.trim().length < 10}
            onClick={() => act(() => api.put<KeyStatus>(PATH, { key }), 'Key tested and saved.')}
          >
            Test and save
          </button>
          <button
            disabled={busy || !status?.saved}
            onClick={() => act(() => api.post<KeyStatus>(`${PATH}/test`), 'The saved key works.')}
          >
            Test saved key
          </button>
          <button
            disabled={busy || !status?.saved}
            onClick={() => act(() => api.delete<KeyStatus>(PATH), 'Key removed from the keychain.')}
          >
            Remove
          </button>
        </div>
        {note && !error && <p className="ok">{note}</p>}
        {error && <p className="error">{error}</p>}
      </section>
    </div>
  )
}
