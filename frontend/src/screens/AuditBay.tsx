import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { AuditState } from '../api/types'
import { useEvents } from '../api/useEvents'
import { useAction } from '../components/useAction'

export const AUDIT_CHANNEL = -1

function stateWord(pr: AuditState['prs'][number]) {
  if (pr.state === 'merged') return 'MERGED'
  if (pr.state === 'open') return 'READY TO REVIEW'
  return pr.state.toUpperCase()
}

// Plain audit bay (phase 7): the pixel room arrives in phase 8.
export function AuditBay() {
  const [state, setState] = useState<AuditState | null>(null)
  const events = useEvents(AUDIT_CHANNEL)
  const { busy, error, run } = useAction()
  const load = useCallback(() => api.get<AuditState>('/api/audit').then(setState), [])

  useEffect(() => void load(), [load, events.version])

  if (!state) return <p className="mute">Loading…</p>
  const current = state.current
  return (
    <div className="audit">
      <section className="panel stack">
        <header className="row spread">
          <h1>Audit bay</h1>
          <p className="pixel-status" aria-live="polite">
            {current ? current.stage : 'OFFLINE'}
          </p>
        </header>
        <p className="mute">
          The audit crew reads the logs of every agent call, files issues, and proposes fixes as
          GitHub pull requests. Only small template and quiz wording changes that pass every safety
          rule merge on their own.
        </p>
        {!state.github && (
          <p className="warning">
            No GitHub token is saved, so fixes are recorded but no pull requests are opened. Add one
            in Core access.
          </p>
        )}
        <div className="row">
          <button
            className="primary"
            disabled={busy || current !== null}
            onClick={() =>
              run(() => api.post<AuditState>('/api/audit/run')).then((s) => s && setState(s))
            }
          >
            {current
              ? `${current.kind === 'deep' ? 'Deep' : 'Project'} scan running…`
              : 'Run a deep scan now'}
          </button>
          <span className="mute">
            Next deep scan:{' '}
            {state.next_deep_scan
              ? state.next_deep_scan.slice(0, 10)
              : 'when there are calls to audit'}
          </span>
        </div>
        {error && <p className="error">{error}</p>}
      </section>
      <section className="panel stack" aria-label="Issues">
        <h2>Intel board</h2>
        {state.issues.length === 0 && <p className="mute">No issues yet.</p>}
        <ul className="audit-list">
          {state.issues.map((i) => (
            <li key={i.id} className={i.severity}>
              <span className="tag">{i.severity}</span> {i.title}
              <span className="mute"> · {i.agent}</span>
            </li>
          ))}
        </ul>
      </section>
      <section className="panel stack" aria-label="Pull requests">
        <h2>PR board</h2>
        {state.prs.length === 0 && <p className="mute">No pull requests yet.</p>}
        <ul className="audit-list">
          {state.prs.map((p) => (
            <li key={p.id}>
              <span className="tag">{stateWord(p)}</span>{' '}
              {p.pr_url ? <a href={p.pr_url}>{p.branch}</a> : p.branch}
            </li>
          ))}
        </ul>
      </section>
      <section className="panel stack" aria-label="Runs">
        <h2>Runs</h2>
        <ul className="audit-list">
          {state.runs.map((r) => (
            <li key={r.id}>
              #{r.id} {r.kind} scan · {r.status} · {r.started_at}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export function AuditPill() {
  const [state, setState] = useState<AuditState | null>(null)
  const events = useEvents(AUDIT_CHANNEL)
  useEffect(() => {
    api
      .get<AuditState>('/api/audit')
      .then(setState)
      .catch(() => setState(null)) // the pill is a hint; mission control works without it
  }, [events.version])
  const current = state?.current
  const label = current ? (current.kind === 'deep' ? 'Deep scan' : 'Project scan') : 'Offline'
  const open = state?.prs.filter((p) => p.state === 'open').length ?? 0
  return (
    <Link
      to="/audit"
      className={`audit-pill ${current?.kind ?? 'offline'}`}
      aria-label={`Audit: ${label}`}
    >
      <span className="light-dot" aria-hidden="true" /> Audit · {label}
      {current && <span className="mute"> · {current.stage}</span>}
      {!current && open > 0 && <span className="mute"> · {open} to review</span>}
    </Link>
  )
}
