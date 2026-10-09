import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { AuditState } from '../api/types'
import { useEvents } from '../api/useEvents'
import { useAction } from '../components/useAction'
import { AuditRoom, type IssueCard, type Mode, type Picked, type PrCard } from '../scenes/auditRoom'
import { useFrame, useReducedMotion } from '../scenes/canvas'

export const AUDIT_CHANNEL = -1

function stateWord(pr: AuditState['prs'][number]) {
  if (pr.state === 'merged') return 'MERGED'
  if (pr.state === 'open') return 'READY TO REVIEW'
  return pr.state.toUpperCase()
}

function issueCards(state: AuditState): IssueCard[] {
  return state.issues.map((i) => ({
    key: `i${i.id}`,
    id: `I-${i.id}`,
    tag: i.agent.toUpperCase(),
    title: i.title,
    state: i.status === 'open' ? 'open' : i.status === 'fixed' ? 'fixed' : 'repair',
  }))
}

function prCards(state: AuditState): PrCard[] {
  return state.prs.map((p) => ({
    key: `p${p.id}`,
    id: `#${p.id}`,
    tag: p.branch.split('/').at(-1)?.toUpperCase() ?? '',
    title: p.branch,
    state: p.state === 'merged' ? 'merged' : p.state === 'open' ? 'ready' : 'tests',
    url: p.pr_url,
  }))
}

function Room({
  state,
  siren,
  onPick,
}: {
  state: AuditState
  siren: number
  onPick: (p: Picked) => void
}) {
  const ref = useRef<HTMLCanvasElement>(null)
  const room = useRef<AuditRoom | null>(null)
  const still = useReducedMotion()
  const mode: Mode = state.current ? (state.current.kind === 'deep' ? 'deep' : 'quick') : 'offline'

  useEffect(() => {
    if (ref.current && !room.current) room.current = new AuditRoom(ref.current)
    const r = room.current
    if (!r) return
    r.setMode(mode)
    r.setBoards(issueCards(state), prCards(state))
    r.alarm = state.issues.some((i) => i.severity === 'high' && i.status === 'open')
  }, [state, mode])

  useEffect(() => {
    if (siren) room.current?.siren()
  }, [siren])

  const last = useRef(0)
  const draw = useCallback(
    (now: number) => {
      const dt = last.current ? Math.min(0.05, (now - last.current) / 1000) : 0
      last.current = now
      room.current?.frame(now, still, dt)
    },
    [still],
  )
  useFrame(draw, still)

  const open = state.issues.filter((i) => i.status === 'open').length
  return (
    <canvas
      ref={ref}
      className="audit-room"
      role="img"
      aria-label={`Audit bay, ${mode === 'offline' ? 'offline, agents resting' : `${mode === 'deep' ? 'deep' : 'project'} scan: ${state.current?.stage ?? ''}`}. ${open} open issues, ${state.prs.length} pull requests.`}
      onPointerMove={(e) => room.current?.move(e.clientX, e.clientY)}
      onPointerLeave={() => room.current?.leave()}
      onClick={(e) => {
        const p = room.current?.click(e.clientX, e.clientY)
        if (p && p.kind !== 'agent') onPick(p)
      }}
    />
  )
}

export function AuditBay() {
  const [state, setState] = useState<AuditState | null>(null)
  const events = useEvents(AUDIT_CHANNEL)
  const { busy, error, run } = useAction()
  const [picked, setPicked] = useState<Picked | null>(null)
  const load = useCallback(() => api.get<AuditState>('/api/audit').then(setState), [])
  const sirens = events.lines.filter((l) => l.text.startsWith('high-severity issue')).length

  useEffect(() => void load(), [load, events.version])

  if (!state) return <p className="mute">Loading…</p>
  const current = state.current
  return (
    <div className="audit">
      <Room state={state} siren={sirens} onPick={setPicked} />
      {picked && picked.kind !== 'agent' && (
        <p className="panel picked" aria-live="polite">
          <strong>{picked.card.id}</strong> {picked.card.title}
          {picked.kind === 'pr' && picked.card.url && (
            <>
              {' '}
              <a href={picked.card.url}>Open on GitHub</a>
            </>
          )}
        </p>
      )}
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

// The corner popup in mission control (AuditPopups.dc.html): asleep, a quiet project scan,
// or a loud deep scan with live counts. The red dot shows only when this run pinned something.
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
  const kind = current?.kind ?? 'offline'
  const label = current ? (kind === 'deep' ? 'Deep scan' : 'Project scan') : 'Offline'
  const toReview = state?.prs.filter((p) => p.state === 'open').length ?? 0
  const issues = state?.issues.filter((i) => i.run_id === current?.run_id).length ?? 0
  const fixes = state?.prs.filter((p) => p.run_id === current?.run_id).length ?? 0
  return (
    <Link to="/audit" className={`audit-pill ${kind}`} aria-label={`Audit: ${label}`}>
      {kind === 'offline' && <span className="sd" aria-hidden="true" />}
      {kind === 'project' && <span className="ring" aria-hidden="true" />}
      {kind === 'deep' && <span className="radar" aria-hidden="true" />}
      <span className="pill-text">
        <span className="pill-title">{current ? label : 'Audit bay / offline'}</span>
        {current && <span className="pill-sub">{current.stage}</span>}
        {kind === 'deep' && (
          <span className="pill-sub">
            {issues} {issues === 1 ? 'issue' : 'issues'} / {fixes} {fixes === 1 ? 'fix' : 'fixes'}{' '}
            so far
          </span>
        )}
        {!current && toReview > 0 && <span className="pill-sub">{toReview} to review</span>}
      </span>
      {!current && (
        <span className="zz" aria-hidden="true">
          z z
        </span>
      )}
      {current && issues > 0 && <span className="dot" aria-hidden="true" />}
    </Link>
  )
}
