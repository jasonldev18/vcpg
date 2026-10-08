import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Project, Step } from '../api/types'
import { type Events, useEvents } from '../api/useEvents'
import { BuildNoteView, BuildPanel } from '../components/BuildPanel'
import { Console } from '../components/Console'
import { GatePanel } from '../components/GatePanel'
import { PlanReview } from '../components/PlanReview'
import { TeachPanel } from '../components/TeachPanel'
import { useAction } from '../components/useAction'

const STATE_LABEL: Record<string, string> = {
  planned: 'teach',
  taught: 'build',
  built: 'review',
  reviewed: 'tour',
  toured: 'gate',
  interviewing: 'gate',
  passed: 'slide',
  slide_done: 'done',
  blocked: 'blocked',
}

function StepList({ steps, currentId }: { steps: Step[]; currentId: number | null }) {
  return (
    <nav className="panel step-list" aria-label="Steps">
      <h2>Steps</h2>
      <ol>
        {steps.map((s) => (
          <li
            key={s.id}
            className={
              s.id === currentId ? 'current' : s.state === 'slide_done' ? 'done' : 'locked'
            }
          >
            <span>{s.title}</span>
            <span className="state">
              {s.id === currentId || s.state === 'slide_done' ? STATE_LABEL[s.state] : 'locked'}
            </span>
          </li>
        ))}
      </ol>
    </nav>
  )
}

// Stand-in for the code tour until phase 3: shows the build note.
function TourPlaceholder({ step, onChange }: { step: Step; onChange: (s: Step) => void }) {
  const { busy, error, run } = useAction()
  const go = () =>
    run(() =>
      api.post<Step>(`/api/steps/${step.id}/advance`, { action: 'ready_for_interview' }),
    ).then((s) => s && onChange(s))
  return (
    <section className="panel stack">
      <p className="kicker">Step {step.position + 1} · code tour</p>
      <h1>{step.title}</h1>
      {step.build_note && <BuildNoteView note={step.build_note} />}
      <p className="mute">{step.review_note}</p>
      <button className="primary" disabled={busy} onClick={go}>
        {busy ? 'Opening the interview…' : "I'm ready for the interview"}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function CurrentPanel({
  step,
  events,
  onChange,
}: {
  step: Step
  events: Events
  onChange: (s: Step) => void
}) {
  const { live } = events
  if (step.state === 'planned')
    return <TeachPanel step={step} live={live.tutor} onChange={onChange} />
  if (step.state === 'taught' || step.state === 'built')
    return <BuildPanel step={step} lines={events.lines} onChange={onChange} />
  if (step.state === 'reviewed' || step.state === 'toured')
    return <TourPlaceholder step={step} onChange={onChange} />
  return <GatePanel step={step} live={live} onChange={onChange} />
}

export function MissionControl() {
  const [project, setProject] = useState<Project | null | undefined>(undefined)
  const [step, setStep] = useState<Step | null>(null)
  const [error, setError] = useState<string | null>(null)
  const events = useEvents(project?.id ?? null)

  const load = useCallback(
    () =>
      api
        .get<Project | null>('/api/projects/current')
        .then(setProject)
        .catch((e: Error) => setError(e.message)),
    [],
  )
  useEffect(() => void load(), [load])

  const currentId = project?.current_step_id ?? null
  useEffect(() => {
    if (currentId === null) return
    void api.get<Step>(`/api/steps/${currentId}`).then(setStep)
  }, [currentId, events.version]) // builds finish in the background

  const onStep = useCallback(
    (s: Step) => {
      setStep(s)
      if (s.state === 'slide_done') void load() // gate passed: the next step unlocks
    },
    [load],
  )

  const shown = currentId !== null && step?.id === currentId ? step : null

  if (error) return <p className="error">Could not reach the API: {error}</p>
  if (project === undefined) return <p className="mute">Loading…</p>
  if (project === null)
    return (
      <section className="panel stack">
        <h1>Mission control</h1>
        <p>No project yet.</p>
        <Link to="/start">Start a project</Link>
      </section>
    )
  if (project.plan)
    return (
      <PlanReview
        key={JSON.stringify(project.plan)}
        project={project}
        plan={project.plan}
        onChange={setProject}
      />
    )

  return (
    <div className="mission">
      <StepList steps={project.steps} currentId={currentId} />
      <div className="current">
        {shown ? (
          <CurrentPanel key={shown.id} step={shown} events={events} onChange={onStep} />
        ) : (
          <section className="panel">
            <h1>{currentId === null ? 'Every step has passed its gate' : 'Loading…'}</h1>
          </section>
        )}
      </div>
      <Console lines={events.lines} live={events.live} />
    </div>
  )
}
