import { useState } from 'react'
import { api } from '../api/client'
import type { Project, Step } from '../api/types'
import { BuildNoteView } from './BuildPanel'
import { useAction } from './useAction'

interface Props {
  step: Step
  onStep: (s: Step) => void
  onProject: (p: Project) => void
}

export function BlockedPanel({ step, onStep, onProject }: Props) {
  const [request, setRequest] = useState('')
  const { busy, error, run } = useAction()
  const review = step.review_note

  const retry = () =>
    run(() => api.post<Step>(`/api/steps/${step.id}/advance`, { action: 'retry' })).then(
      (s) => s && onStep(s),
    )
  const editPlan = () =>
    run(() => api.post<Project>(`/api/projects/${step.project_id}/replan`, { request })).then(
      (p) => p && onProject(p),
    )

  return (
    <section className="panel stack" aria-label="Blocked step">
      <p className="kicker">Step {step.position + 1} · blocked</p>
      <h1>{step.title}</h1>
      <p>The reviewer failed this step twice. Read both notes, then retry or change the plan.</p>
      {step.build_note && <BuildNoteView note={step.build_note} />}
      {review && (
        <div>
          <h2>What the reviewer found</h2>
          <p className="error">{review.failure}</p>
          <ul>
            {review.commands.map((c) => (
              <li key={c.cmd}>
                <code>{c.cmd}</code>: {c.result}, {c.summary}
              </li>
            ))}
          </ul>
        </div>
      )}
      <button className="primary" disabled={busy} onClick={retry}>
        Retry build
      </button>
      <label className="field">
        <span>Edit plan: tell the planner what to change</span>
        <textarea value={request} onChange={(e) => setRequest(e.target.value)} />
      </label>
      <button disabled={busy || !request.trim()} onClick={editPlan}>
        {busy ? 'The planner is revising…' : 'Edit plan'}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export function ReplanReview({
  project,
  onProject,
}: {
  project: Project
  onProject: (p: Project) => void
}) {
  const { busy, error, run } = useAction()
  const replan = project.replan
  if (!replan) return null
  const act = (call: () => Promise<Project>) => run(call).then((p) => p && onProject(p))

  return (
    <section className="panel stack" aria-label="Plan revision">
      <h1>Proposed plan change</h1>
      <p className="mute">Passed steps stay as they are. Only the remaining steps change.</p>
      <div className="replan">
        <div>
          <h2>Now</h2>
          <ol>
            {replan.old.map((s) => (
              <li key={s.title}>
                <strong>{s.title}</strong>: {s.goal}
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h2>Proposed</h2>
          <ol>
            {replan.new.map((s) => (
              <li key={s.title}>
                <strong>{s.title}</strong>: {s.goal}
              </li>
            ))}
          </ol>
        </div>
      </div>
      {replan.changes.length > 0 && (
        <ul>
          {replan.changes.map((c) => (
            <li key={c.step + c.change}>
              {c.step} ({c.change}): {c.reason}
            </li>
          ))}
        </ul>
      )}
      <div className="row">
        <button
          className="primary"
          disabled={busy}
          onClick={() => act(() => api.post<Project>(`/api/projects/${project.id}/replan/approve`))}
        >
          Approve change
        </button>
        <button
          disabled={busy}
          onClick={() => act(() => api.delete<Project>(`/api/projects/${project.id}/replan`))}
        >
          Discard
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
