import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useContext, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Project, Step } from '../api/types'
import { type Events, useEvents } from '../api/useEvents'
import { AuditPill } from './AuditBay'
import { OpenCore } from '../coreContext'
import { CoreNetwork } from '../scenes/CoreNetwork'
import { BlockedPanel, ReplanReview } from '../components/Blocked'
import { BuildPanel } from '../components/BuildPanel'
import { FinishPanel } from '../components/FinishPanel'
import { TourPanel } from '../components/TourPanel'
import { useAction } from '../components/useAction'
import { Console } from '../components/Console'
import { GatePanel } from '../components/GatePanel'
import { PlanReview } from '../components/PlanReview'
import { TeachPanel } from '../components/TeachPanel'

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

// The step hand-off (DESIGN 3.4): a step's chip shares a layoutId between its row and the
// deck counter, so when the step finishes Motion flies the chip into the deck.
const HANDOFF = { duration: 0.45, ease: [0.2, 0.8, 0.2, 1] } as const

function StepList({ steps, currentId }: { steps: Step[]; currentId: number | null }) {
  const done = steps.filter((s) => s.state === 'slide_done')
  return (
    <nav className="panel step-list" aria-label="Steps">
      <h2>Steps</h2>
      <p className="deck-counter" aria-label={`Deck: ${done.length} of ${steps.length} slides`}>
        <span className="deck-chips" aria-hidden="true">
          {done.map((s) => (
            <motion.span
              key={s.id}
              layoutId={`chip-${s.id}`}
              transition={HANDOFF}
              className="chip-dot"
            />
          ))}
        </span>
        Deck {done.length}/{steps.length}
      </p>
      <ol>
        {steps.map((s) => {
          const isDone = s.state === 'slide_done'
          return (
            <li key={s.id} className={s.id === currentId ? 'current' : isDone ? 'done' : 'locked'}>
              <span>{s.title}</span>
              {isDone ? (
                <span className="state">done</span>
              ) : (
                <motion.span layoutId={`chip-${s.id}`} transition={HANDOFF} className="state">
                  {s.id === currentId ? STATE_LABEL[s.state] : 'locked'}
                </motion.span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

// The gate passed but writing the slide failed: let the user retry it.
function PassedPanel({ step, onChange }: { step: Step; onChange: (s: Step) => void }) {
  const { busy, error, run } = useAction()
  const retry = () =>
    run(() => api.post<Step>(`/api/steps/${step.id}/advance`, { action: 'slide' })).then(
      (s) => s && onChange(s),
    )
  return (
    <section className="panel stack">
      <p className="kicker">Step {step.position + 1} · slide</p>
      <h1>Gate passed</h1>
      <p>The slide for this step could not be written yet.</p>
      <button className="primary" disabled={busy} onClick={retry}>
        {busy ? 'Writing the slide…' : 'Write the slide'}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function CurrentPanel({
  step,
  events,
  onChange,
  onProject,
}: {
  step: Step
  events: Events
  onChange: (s: Step) => void
  onProject: (p: Project) => void
}) {
  const { live } = events
  if (step.state === 'planned')
    return <TeachPanel step={step} live={live.tutor} onChange={onChange} />
  if (step.state === 'taught' || step.state === 'built')
    return <BuildPanel step={step} lines={events.lines} onChange={onChange} />
  if (step.state === 'reviewed' || step.state === 'toured')
    return <TourPanel step={step} live={live.tutor} onChange={onChange} />
  if (step.state === 'blocked')
    return <BlockedPanel step={step} onStep={onChange} onProject={onProject} />
  if (step.state === 'passed') return <PassedPanel step={step} onChange={onChange} />
  return <GatePanel step={step} live={live} onChange={onChange} />
}

export function MissionControl() {
  const [project, setProject] = useState<Project | null | undefined>(undefined)
  const [step, setStep] = useState<Step | null>(null)
  const [error, setError] = useState<string | null>(null)
  const events = useEvents(project?.id ?? null)
  const openCore = useContext(OpenCore)

  const load = useCallback(
    () =>
      api
        .get<Project | null>('/api/projects/current')
        .then(setProject)
        .catch((e: Error) => setError(e.message)),
    [],
  )
  useEffect(() => void load(), [load, events.version]) // stages change in the background

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
  const active = new Set(Object.keys(events.live))
  const youTurn =
    active.size === 0 &&
    !shown?.build?.running &&
    (shown !== null || project?.finish?.stage === 'retest')

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
      <div className="current stack">
        <section className="panel stage-panel">
          <header className="row spread">
            <h2>Agent network</h2>
            <span className="mono mute">
              state: {shown?.state ?? project.finish?.stage ?? 'idle'}
            </span>
          </header>
          <CoreNetwork active={active} youTurn={youTurn} onCore={openCore} />
          <p className={youTurn ? 'who you' : 'who'} aria-live="polite">
            [ {youTurn ? 'YOUR TURN' : 'AGENTS WORKING'} ]
          </p>
        </section>
        <ReplanReview project={project} onProject={setProject} />
        {shown ? (
          <AnimatePresence mode="wait">
            <motion.div
              key={`${shown.id}:${shown.state}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22 }}
            >
              <CurrentPanel step={shown} events={events} onChange={onStep} onProject={setProject} />
            </motion.div>
          </AnimatePresence>
        ) : project.finish ? (
          <FinishPanel
            project={project}
            finish={project.finish}
            live={events.live}
            onProject={setProject}
          />
        ) : (
          <section className="panel">
            <h1>Loading…</h1>
          </section>
        )}
      </div>
      <div className="stack">
        <AuditPill />
        <Console lines={events.lines} live={events.live} />
      </div>
    </div>
  )
}
