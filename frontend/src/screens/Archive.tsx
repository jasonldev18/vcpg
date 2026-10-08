import { useEffect, useState } from 'react'
import { api, API_BASE } from '../api/client'
import type { ArchivedProject, MockInterview } from '../api/types'
import { Markdown } from '../components/Markdown'
import { useAction } from '../components/useAction'

const FOCUS = {
  deep_dive: 'Project deep dive',
  system_design: 'System design',
  behavioral: 'Behavioral',
}
const DIMENSION = {
  system_design: 'System design',
  failure_modes: 'Failure modes',
  motivation_and_impact: 'Motivation and impact',
  communication: 'Communication',
}

function clock(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

function Interview({
  mock,
  onChange,
}: {
  mock: MockInterview
  onChange: (m: MockInterview) => void
}) {
  const [answer, setAnswer] = useState('')
  const [left, setLeft] = useState(mock.seconds_left)
  const { busy, error, run } = useAction()

  // Remounted on every server update (see the key below), so it starts from the server clock.
  useEffect(() => {
    if (mock.ended) return
    const timer = window.setInterval(() => setLeft((s) => Math.max(s - 1, 0)), 1000)
    return () => window.clearInterval(timer)
  }, [mock.ended])

  const send = async () => {
    const m = await run(() => api.post<MockInterview>(`/api/mock/${mock.id}/answer`, { answer }))
    if (m) {
      onChange(m)
      setAnswer('')
    }
  }
  const end = () =>
    run(() => api.post<MockInterview>(`/api/mock/${mock.id}/end`)).then((m) => m && onChange(m))

  return (
    <div className="teach">
      <section className="panel gate" aria-label="Mock interview">
        <header className="row spread">
          <h2>
            {FOCUS[mock.focus]} · {mock.length_min} minutes
          </h2>
          <p className="progress" aria-live="off">
            {mock.ended ? 'Ended' : `${clock(left)} left`}
          </p>
        </header>
        <div className="messages">
          {mock.transcript.map((t, i) => (
            <div key={i} className={`msg ${t.role === 'learner' ? 'user' : 'assistant'}`}>
              <span className="who">{t.role === 'learner' ? 'You' : 'Interviewer'}</span>
              <p>{t.text}</p>
            </div>
          ))}
        </div>
        {!mock.ended && (
          <>
            <textarea
              className="you"
              aria-label="Your answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
            />
            <div className="row">
              <button className="primary" disabled={busy || !answer.trim()} onClick={send}>
                Send answer
              </button>
              <button disabled={busy} onClick={end}>
                End and score
              </button>
            </div>
          </>
        )}
        {error && <p className="error">{error}</p>}
      </section>
      <aside className="panel stack" aria-label="Scorecard">
        <h2>Scorecard</h2>
        {!mock.scorecard && <p className="mute">Scores appear after your first answer.</p>}
        {mock.scorecard && (
          <>
            <ul className="scorecard">
              {mock.scorecard.dimensions.map((d) => (
                <li key={d.name}>
                  <strong>
                    {DIMENSION[d.name]}: {d.score} / 5
                  </strong>
                  {d.evidence && <blockquote>“{d.evidence}”</blockquote>}
                  <p className="mute">{d.reason}</p>
                </li>
              ))}
            </ul>
            {mock.ended && (
              <>
                <h3>Practise next</h3>
                <ul>
                  {mock.scorecard.practise.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </aside>
    </div>
  )
}

export function Archive() {
  const [projects, setProjects] = useState<ArchivedProject[] | null>(null)
  const [selected, setSelected] = useState(0)
  const [tab, setTab] = useState<'dossier' | 'readme'>('dossier')
  const [length, setLength] = useState<10 | 20 | 30>(20)
  const [focus, setFocus] = useState<MockInterview['focus']>('deep_dive')
  const [mock, setMock] = useState<MockInterview | null>(null)
  const { busy, error, run } = useAction()

  useEffect(() => {
    void api.get<ArchivedProject[]>('/api/archive').then(setProjects)
  }, [])

  if (projects === null) return <p className="mute">Loading…</p>
  if (projects.length === 0)
    return (
      <section className="panel stack">
        <h1>Archive</h1>
        <p className="mute">Finished projects appear here once their README passes the coach.</p>
      </section>
    )

  const project = projects[selected]
  const start = () =>
    run(() =>
      api.post<MockInterview>(`/api/archive/${project.id}/mock`, { length_min: length, focus }),
    ).then((m) => m && setMock(m))

  return (
    <div className="stack">
      <div className="archive">
        <nav className="panel" aria-label="Finished projects">
          <h1>Archive</h1>
          <ol className="deck-strip">
            {projects.map((p, i) => (
              <li key={p.id}>
                <button
                  className={i === selected ? 'current' : undefined}
                  onClick={() => setSelected(i)}
                >
                  {p.name}
                  <span className="kicker">{p.stack.join(', ')}</span>
                  <span className="kicker">{p.finished_at?.slice(0, 10)}</span>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <section className="panel stack">
          <div className="row">
            <button
              className={tab === 'dossier' ? 'current' : undefined}
              onClick={() => setTab('dossier')}
            >
              Dossier
            </button>
            <button
              className={tab === 'readme' ? 'current' : undefined}
              onClick={() => setTab('readme')}
            >
              README
            </button>
          </div>
          <Markdown text={(tab === 'dossier' ? project.dossier : project.readme) ?? ''} />
        </section>
        <aside className="panel stack">
          <h2>Deck</h2>
          <ul>
            {project.exports.map((e) => (
              <li key={e.id}>
                <a href={`${API_BASE}/api/exports/${e.id}/download`}>
                  deck_v{e.version}.{e.format}
                </a>
              </li>
            ))}
          </ul>
          <h2>Mock interview</h2>
          <label className="field">
            <span>Length</span>
            <select
              value={length}
              onChange={(e) => setLength(Number(e.target.value) as 10 | 20 | 30)}
            >
              {[10, 20, 30].map((n) => (
                <option key={n} value={n}>
                  {n} minutes
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Focus</span>
            <select
              value={focus}
              onChange={(e) => setFocus(e.target.value as MockInterview['focus'])}
            >
              {Object.entries(FOCUS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={busy} onClick={start}>
            {busy ? 'Starting…' : 'Start the interview'}
          </button>
          {error && <p className="error">{error}</p>}
        </aside>
      </div>
      {mock && (
        <Interview
          key={`${mock.id}:${mock.transcript.length}:${mock.ended}`}
          mock={mock}
          onChange={setMock}
        />
      )}
    </div>
  )
}
