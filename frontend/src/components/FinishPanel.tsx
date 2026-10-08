import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Finish, Project } from '../api/types'
import { Markdown } from './Markdown'
import { useAction } from './useAction'

interface Props {
  project: Project
  finish: Finish
  live: Record<string, string>
  onProject: (p: Project) => void
}

const SPEAKER = { user: 'You', assistant: 'Interviewer', reteach: 'Tutor' }

function FinalReview({ project, finish, onProject }: Props) {
  const { busy, error, run } = useAction()
  const status = finish.final_review_status
  const note = finish.final_review
  const start = () =>
    run(() => api.post<Project>(`/api/projects/${project.id}/final-review`)).then(
      (p) => p && onProject(p),
    )
  return (
    <section className="panel stack" aria-label="Final review">
      <p className="kicker">End of project · final review</p>
      <h1>Every step has passed its gate</h1>
      <p>
        The reviewer now runs the whole test suite and one end-to-end trial of the finished app.
      </p>
      {status.running && <p aria-live="polite">The reviewer is checking the whole project…</p>}
      {note && note.status === 'fail' && <p className="error">{note.failure}</p>}
      {status.error && <p className="error">{status.error}</p>}
      {!status.running && (
        <button className="primary" disabled={busy} onClick={start}>
          {note || status.error ? 'Run the final review again' : 'Start the final review'}
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function Retest({ project, finish, live, onProject }: Props) {
  const [answer, setAnswer] = useState('')
  const { busy, error, run } = useAction()
  const retest = finish.retest
  const started = useRef(false)
  const base = `/api/projects/${project.id}/retest`

  useEffect(() => {
    if (started.current || !retest || retest.messages.length > 0 || !retest.current_step) return
    started.current = true
    void run(() => api.post<Project>(`${base}/start`)).then((p) => p && onProject(p))
  }, [retest, base, run, onProject])

  if (!retest) return null
  const send = async () => {
    const p = await run(() => api.post<Project>(`${base}/answer`, { answer }))
    if (p) {
      onProject(p)
      setAnswer('')
    }
  }
  const prepare = () =>
    run(() => api.post<Project>(`/api/projects/${project.id}/deck/prepare`)).then(
      (p) => p && onProject(p),
    )

  return (
    <section className="panel gate" aria-label="Re-test">
      <header className="row spread">
        <div>
          <p className="kicker">End of project · re-test</p>
          <h1>{retest.current_step ?? 'Re-test complete'}</h1>
        </div>
        <p className="progress" aria-live="polite">
          {retest.passed} of {retest.total} steps re-tested
        </p>
      </header>
      <p className="mute">One question per step, on the point you found hardest at its gate.</p>
      <div className="messages">
        {retest.messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <span className="who">{SPEAKER[m.role]}</span>
            {m.role === 'user' ? <p>{m.content}</p> : <Markdown text={m.content} />}
          </div>
        ))}
        {busy && (
          <div className="msg assistant pending">
            <Markdown text={live.tutor ?? live.interviewer ?? '_Thinking…_'} />
          </div>
        )}
      </div>
      {retest.current_step ? (
        <>
          <textarea
            className="you"
            aria-label="Your answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
          <button className="primary" disabled={busy || !answer.trim()} onClick={send}>
            Send answer
          </button>
        </>
      ) : (
        <button className="primary" disabled={busy} onClick={prepare}>
          Write the title, overview and retrospective slides
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export function FinishPanel(props: Props) {
  const { project, finish, onProject } = props
  const { busy, error, run } = useAction()
  if (finish.stage === 'final_review') return <FinalReview {...props} />
  if (finish.stage === 'retest') return <Retest {...props} />
  if (finish.stage === 'deck')
    return (
      <section className="panel stack" aria-label="Deck">
        <p className="kicker">End of project · deck</p>
        <h1>Your interview deck is ready</h1>
        <p>Review the slides, edit them in your own words, and export to PowerPoint or PDF.</p>
        <Link to="/deck">Open the deck viewer</Link>
        <button
          className="primary"
          disabled={busy}
          onClick={() =>
            run(() => api.post<Project>(`/api/projects/${project.id}/deck/done`)).then(
              (p) => p && onProject(p),
            )
          }
        >
          Continue to the README
        </button>
        {error && <p className="error">{error}</p>}
      </section>
    )
  return (
    <section className="panel stack">
      <p className="kicker">End of project · README</p>
      <h1>README coach</h1>
      <p className="mute">The README coach arrives in phase 5.</p>
    </section>
  )
}
