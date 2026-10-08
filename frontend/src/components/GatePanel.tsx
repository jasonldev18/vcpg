import { useState } from 'react'
import { api } from '../api/client'
import type { Step } from '../api/types'
import { Markdown } from './Markdown'
import { useAction } from './useAction'

interface Props {
  step: Step
  live: Record<string, string>
  onChange: (s: Step) => void
}

const SPEAKER = { user: 'You', assistant: 'Interviewer', reteach: 'Tutor' }

export function GatePanel({ step, live, onChange }: Props) {
  const [answer, setAnswer] = useState('')
  const { busy, error, run } = useAction()
  const act = (path: string, body?: unknown) =>
    run(() => api.post<Step>(`/api/steps/${step.id}/${path}`, body)).then((s) => {
      if (s) onChange(s)
      return s
    })
  const send = async () => {
    if (await act('gate/answer', { answer })) setAnswer('')
  }
  const streaming = live.tutor ?? live.interviewer
  const { covered, total } = step.progress

  return (
    <section className="panel gate" aria-label="Interview gate">
      <header className="row spread">
        <div>
          <p className="kicker">Step {step.position + 1} · interview gate</p>
          <h1>{step.title}</h1>
        </div>
        <p className="progress" aria-live="polite">
          {covered} of {total} points covered
        </p>
      </header>
      <div className="messages">
        {step.gate.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <span className="who">{SPEAKER[m.role]}</span>
            {m.role === 'user' ? <p>{m.content}</p> : <Markdown text={m.content} />}
          </div>
        ))}
        {busy && (
          <div className="msg assistant pending">
            <Markdown text={streaming || '_Thinking…_'} />
          </div>
        )}
      </div>
      <textarea
        className="you"
        aria-label="Your answer"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="Answer in your own words"
      />
      <div className="row">
        <button className="primary" disabled={busy || !answer.trim()} onClick={send}>
          Send answer
        </button>
        <button disabled={busy || !step.can_hint} onClick={() => act('gate/hint')}>
          Hint
        </button>
        <button disabled={busy} onClick={() => act('gate/reteach')}>
          Teach me this again
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
