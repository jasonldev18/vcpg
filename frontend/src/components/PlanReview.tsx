import { useState } from 'react'
import { api } from '../api/client'
import type { PlanView, Project } from '../api/types'
import { useAction } from './useAction'

interface Props {
  project: Project
  plan: PlanView
  onChange: (p: Project) => void
}

function Questions({ project, plan, onChange }: Props) {
  const [answers, setAnswers] = useState(plan.questions.map(() => ''))
  const { busy, error, run } = useAction()
  const submit = () =>
    run(() => api.post<Project>(`/api/projects/${project.id}/plan/answers`, { answers })).then(
      (p) => p && onChange(p),
    )

  return (
    <section className="panel stack">
      <h2>The planner has questions</h2>
      {plan.questions.map((q, i) => (
        <label key={q} className="field">
          <span>{q}</span>
          <textarea
            value={answers[i]}
            onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))}
          />
        </label>
      ))}
      <button disabled={busy || answers.some((a) => !a.trim())} onClick={submit}>
        {busy ? 'Planning…' : 'Send answers'}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

interface Row {
  source: number
  title: string
}

export function PlanReview(props: Props) {
  const { project, plan, onChange } = props
  const [rows, setRows] = useState<Row[]>(plan.steps.map((s, i) => ({ source: i, title: s.title })))
  const [request, setRequest] = useState('')
  const { busy, error, run } = useAction()

  if (plan.questions.length > 0) return <Questions {...props} />

  const edited =
    rows.length !== plan.steps.length ||
    rows.some((r, i) => r.source !== i || r.title !== plan.steps[i].title)
  const move = (i: number, by: number) => {
    const next = [...rows]
    ;[next[i], next[i + by]] = [next[i + by], next[i]]
    setRows(next)
  }
  const update = (p: Project | undefined) => {
    if (!p) return
    onChange(p)
    if (p.plan) setRows(p.plan.steps.map((s, i) => ({ source: i, title: s.title })))
  }
  const save = () =>
    run(() => api.put<Project>(`/api/projects/${project.id}/plan`, { steps: rows }))
  const approve = async () => {
    if (edited && !(await save())) return
    update(await run(() => api.post<Project>(`/api/projects/${project.id}/plan/approve`)))
  }
  const revise = async () => {
    update(
      await run(() => api.post<Project>(`/api/projects/${project.id}/plan/revise`, { request })),
    )
    setRequest('')
  }

  return (
    <section className="panel stack">
      <h1>{plan.project_name}</h1>
      <p>{plan.one_liner}</p>
      <p className="mute">Stack: {plan.stack.join(', ')}</p>
      <ol className="plan-steps">
        {rows.map((row, i) => {
          const step = plan.steps[row.source]
          return (
            <li key={row.source}>
              <input
                aria-label={`Title of step ${i + 1}`}
                value={row.title}
                onChange={(e) =>
                  setRows(rows.map((r, j) => (j === i ? { ...r, title: e.target.value } : r)))
                }
              />
              <p>{step.goal}</p>
              <p className="chips">
                {step.concepts.map((c) => (
                  <span key={c} className="chip">
                    {c}
                  </span>
                ))}
              </p>
              <div className="row">
                <button
                  aria-label={`Move step ${i + 1} up`}
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                >
                  ↑
                </button>
                <button
                  aria-label={`Move step ${i + 1} down`}
                  disabled={i === rows.length - 1}
                  onClick={() => move(i, 1)}
                >
                  ↓
                </button>
                <button
                  aria-label={`Drop step ${i + 1}`}
                  disabled={rows.length === 1}
                  onClick={() => setRows(rows.filter((_, j) => j !== i))}
                >
                  Drop
                </button>
              </div>
            </li>
          )
        })}
      </ol>
      {plan.changes_from_spine.length > 0 && (
        <details>
          <summary>Changes from the standard spine</summary>
          <ul>
            {plan.changes_from_spine.map((c) => (
              <li key={c.step + c.change}>
                {c.step} ({c.change}): {c.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
      <label className="field">
        <span>Ask the planner for changes</span>
        <textarea value={request} onChange={(e) => setRequest(e.target.value)} />
      </label>
      <div className="row">
        <button disabled={busy || !request.trim()} onClick={revise}>
          Ask for changes
        </button>
        <button
          className="primary"
          disabled={busy || rows.some((r) => !r.title.trim())}
          onClick={approve}
        >
          Approve plan
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
