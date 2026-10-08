import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { KeyStatus, TokenStatus } from '../api/types'
import { useAction } from './useAction'

function SecretPanel<S extends KeyStatus>({
  path,
  title,
  label,
  placeholder,
  field,
  minLength,
  children,
}: {
  path: string
  title: string
  label: string
  placeholder: string
  field: 'key' | 'token'
  minLength: number
  children?: (status: S) => React.ReactNode
}) {
  const [status, setStatus] = useState<S | null>(null)
  const [value, setValue] = useState('')
  const [note, setNote] = useState<string | null>(null)
  const { busy, error, run } = useAction()

  useEffect(() => {
    void api.get<S>(path).then(setStatus)
  }, [path])

  const act = async (action: () => Promise<S>, done: (s: S) => string) => {
    const s = await run(action)
    if (s) {
      setStatus(s)
      setValue('')
      setNote(done(s))
    }
  }

  return (
    <section className="stack">
      <h2>
        <span className={`light ${status?.saved ? 'on' : 'off'}`} aria-hidden="true" />
        {title}
      </h2>
      <p className="mute">
        {status === null
          ? 'Checking…'
          : status.saved
            ? `Saved in your OS keychain, ending in ${status.last4}.`
            : 'Not saved.'}
      </p>
      <input
        type="password"
        autoComplete="off"
        aria-label={label}
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <div className="row">
        <button
          className="primary"
          disabled={busy || value.trim().length < minLength}
          onClick={() =>
            act(
              () => api.put<S>(path, { [field]: value }),
              (s) => (s.saved ? 'Tested and saved.' : 'Not saved: see the problems below.'),
            )
          }
        >
          Test and save
        </button>
        <button
          disabled={busy || !status?.saved}
          onClick={() =>
            act(
              () => api.post<S>(`${path}/test`),
              () => 'Tested.',
            )
          }
        >
          Test saved
        </button>
        <button
          disabled={busy || !status?.saved}
          onClick={() =>
            act(
              () => api.delete<S>(path),
              () => 'Removed from the keychain.',
            )
          }
        >
          Remove
        </button>
      </div>
      {status && children?.(status)}
      {note && !error && <p className="ok">{note}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export function CoreAccess({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])

  return (
    <motion.div
      className="overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Core access"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22 }}
    >
      <motion.div
        layoutId="core"
        className="core-big"
        aria-hidden="true"
        transition={{ type: 'spring', duration: 0.4, bounce: 0.2 }}
      >
        <i className="k1" />
        <i className="k2" />
        <i className="k3" />
        <i className="k4" />
      </motion.div>
      <motion.section
        className="panel stack core-access"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, delay: 0.12 }}
      >
        <header className="row spread">
          <h1 className="brand">Core access</h1>
          <button onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <SecretPanel<KeyStatus>
          path="/api/core/anthropic"
          title="Anthropic API key"
          label="Paste a new Anthropic API key"
          placeholder="sk-ant-…"
          field="key"
          minLength={10}
        />
        <SecretPanel<TokenStatus>
          path="/api/core/github"
          title="GitHub token"
          label="Paste a fine-grained GitHub token"
          placeholder="github_pat_…"
          field="token"
          minLength={20}
        >
          {(s) => (
            <div className="stack">
              <p className="mute">
                Use a fine-grained token for the vcpg repository only, with Contents and Pull
                requests set to read and write and nothing else. GitHub cannot list a token&apos;s
                permissions, so the check probes for broader access; it cannot see Workflows or
                Actions, so leave those off.
              </p>
              {s.found.length > 0 && (
                <ul aria-label="Permissions found">
                  {s.found.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              )}
              {s.problems.map((p) => (
                <p key={p} className="error">
                  Refused: {p}
                </p>
              ))}
            </div>
          )}
        </SecretPanel>
      </motion.section>
    </motion.div>
  )
}
