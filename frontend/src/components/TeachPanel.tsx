import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Step } from '../api/types'
import { Markdown } from './Markdown'
import { useAction } from './useAction'

interface Props {
  step: Step
  live: string | undefined
  onChange: (s: Step) => void
}

export function TeachPanel({ step, live, onChange }: Props) {
  const [question, setQuestion] = useState('')
  const lesson = useAction()
  const chat = useAction()
  const [attempt, setAttempt] = useState(0)
  const requested = useRef<string | null>(null)

  useEffect(() => {
    const key = `${step.id}:${attempt}`
    if (step.lesson !== null || requested.current === key) return
    requested.current = key // StrictMode runs effects twice; teach once per attempt
    void lesson
      .run(() => api.post<Step>(`/api/steps/${step.id}/teach`))
      .then((s) => s && onChange(s))
  }, [step.id, step.lesson, attempt, lesson, onChange])

  const ask = async () => {
    const s = await chat.run(() => api.post<Step>(`/api/steps/${step.id}/ask`, { question }))
    if (s) {
      onChange(s)
      setQuestion('')
    }
  }
  const ready = () =>
    lesson
      .run(() => api.post<Step>(`/api/steps/${step.id}/advance`, { action: 'ready' }))
      .then((s) => s && onChange(s))

  return (
    <div className="teach">
      <section className="panel lesson">
        <p className="kicker">Step {step.position + 1} · teach</p>
        <h1>{step.title}</h1>
        {step.lesson ? (
          <Markdown text={step.lesson} />
        ) : (
          <Markdown text={live || (lesson.error ? '' : '_The tutor is preparing this lesson…_')} />
        )}
        {lesson.error && (
          <p className="error">
            {lesson.error} <button onClick={() => setAttempt((a) => a + 1)}>Try again</button>
          </p>
        )}
        <button className="primary" disabled={!step.lesson || lesson.busy} onClick={ready}>
          Ready, build it
        </button>
      </section>
      <aside className="panel chat" aria-label="Ask the tutor">
        <h2>Ask the tutor</h2>
        <div className="messages">
          {step.chat.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              {m.role === 'user' ? m.content : <Markdown text={m.content} />}
            </div>
          ))}
          {chat.busy && live && <div className="msg assistant">{live}</div>}
        </div>
        <textarea
          aria-label="Your question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask anything about this step"
        />
        <button disabled={chat.busy || !question.trim()} onClick={ask}>
          {chat.busy ? 'Asking…' : 'Ask'}
        </button>
        {chat.error && <p className="error">{chat.error}</p>}
      </aside>
    </div>
  )
}
