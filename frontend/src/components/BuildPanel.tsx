import { api } from '../api/client'
import type { BuildNote, Step } from '../api/types'
import type { ConsoleLine } from '../api/useEvents'
import { useAction } from './useAction'

interface Props {
  step: Step
  lines: ConsoleLine[]
  onChange: (s: Step) => void
}

export function BuildPanel({ step, lines, onChange }: Props) {
  const { busy, error, run } = useAction()
  const build = step.build
  const act = (action: string) =>
    run(() => api.post<Step>(`/api/steps/${step.id}/advance`, { action })).then(
      (s) => s && onChange(s),
    )
  const actions = lines.filter((l) => l.agent === 'builder').slice(-40)

  return (
    <section className="panel stack" aria-label="Build">
      <p className="kicker">Step {step.position + 1} · build</p>
      <h1>{step.title}</h1>
      {build?.isolation === 'venv' && (
        <p className="warning">
          Docker is not available, so generated code runs in a plain virtual environment. Its
          isolation is weaker than a container.
        </p>
      )}
      <p aria-live="polite">
        {build?.running
          ? build.paused
            ? 'Paused. The builder will wait before its next action.'
            : 'The builder is writing code…'
          : build?.error
            ? 'The build stopped with an error.'
            : 'The build is not running. Your files are kept as they are.'}
      </p>
      <ol className="build-log">
        {actions.map((l) => (
          <li key={l.id}>{l.text}</li>
        ))}
      </ol>
      {build?.error && <p className="error">{build.error}</p>}
      <div className="row">
        {build?.running ? (
          <>
            <button disabled={busy} onClick={() => act(build.paused ? 'resume' : 'pause')}>
              {build.paused ? 'Resume' : 'Pause'}
            </button>
            <button disabled={busy} onClick={() => act('stop')}>
              Stop
            </button>
          </>
        ) : (
          <button className="primary" disabled={busy} onClick={() => act('build')}>
            {build?.error ? 'Retry build' : 'Build'}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export function BuildNoteView({ note }: { note: BuildNote }) {
  return (
    <div className="build-note">
      <h2>What the builder changed</h2>
      <ul>
        {note.files.map((f) => (
          <li key={f.path}>
            <code>{f.path}</code>: {f.summary}
          </li>
        ))}
      </ul>
      {note.decisions.length > 0 && (
        <>
          <h3>Decisions</h3>
          <ul>
            {note.decisions.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </>
      )}
      {note.not_done.length > 0 && (
        <>
          <h3>Not done</h3>
          <ul>
            {note.not_done.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
