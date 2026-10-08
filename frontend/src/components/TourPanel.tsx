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

function CodeView({
  lines,
  start,
  end,
  onLine,
}: {
  lines: string[]
  start: number
  end: number
  onLine: (n: number) => void
}) {
  const first = Math.max(1, start - 4)
  const last = Math.min(lines.length, end + 4)
  return (
    <pre className="code-view" aria-label="Code">
      {lines.slice(first - 1, last).map((text, i) => {
        const n = first + i
        return (
          <div key={n} className={n >= start && n <= end ? 'hl' : undefined}>
            <button
              className="line-no"
              aria-label={`Ask about line ${n}`}
              onClick={() => onLine(n)}
            >
              {n}
            </button>
            <code>{text || ' '}</code>
          </div>
        )
      })}
    </pre>
  )
}

export function TourPanel({ step, live, onChange }: Props) {
  const [index, setIndex] = useState(0)
  const [files, setFiles] = useState<Record<string, string[]>>({})
  const [question, setQuestion] = useState('')
  const tour = useAction()
  const chat = useAction()
  const go = useAction()
  const requested = useRef<number | null>(null)
  const stop = step.tour?.stops[index]

  useEffect(() => {
    if (step.tour || requested.current === step.id) return
    requested.current = step.id
    void tour.run(() => api.post<Step>(`/api/steps/${step.id}/tour`)).then((s) => s && onChange(s))
  }, [step.id, step.tour, tour, onChange])

  useEffect(() => {
    if (!stop || files[stop.file]) return
    const path = encodeURIComponent(stop.file)
    void api
      .get<{ lines: string[] }>(`/api/steps/${step.id}/file?path=${path}`)
      .then((f) => setFiles((all) => ({ ...all, [stop.file]: f.lines })))
  }, [stop, files, step.id])

  const ask = async () => {
    const s = await chat.run(() => api.post<Step>(`/api/steps/${step.id}/ask`, { question }))
    if (s) {
      onChange(s)
      setQuestion('')
    }
  }
  const ready = () =>
    go
      .run(() => api.post<Step>(`/api/steps/${step.id}/advance`, { action: 'ready_for_interview' }))
      .then((s) => s && onChange(s))

  if (!step.tour)
    return (
      <section className="panel stack">
        <p className="kicker">Step {step.position + 1} · code tour</p>
        <h1>{step.title}</h1>
        <p className="mute">{tour.error ? '' : 'The tutor is reading the committed code…'}</p>
        {tour.error && <p className="error">{tour.error}</p>}
      </section>
    )

  return (
    <div className="teach">
      <section className="panel stack tour" aria-label="Code tour">
        <p className="kicker">
          Step {step.position + 1} · code tour · stop {index + 1} of {step.tour.stops.length}
        </p>
        <h1>{step.title}</h1>
        <ol className="stops">
          {step.tour.stops.map((s, i) => (
            <li key={`${s.file}:${s.line_start}`}>
              <button className={i === index ? 'current' : undefined} onClick={() => setIndex(i)}>
                {s.file}:{s.line_start}-{s.line_end}
              </button>
            </li>
          ))}
        </ol>
        {stop && (
          <>
            {files[stop.file] ? (
              <CodeView
                lines={files[stop.file]}
                start={stop.line_start}
                end={stop.line_end}
                onLine={(n) => setQuestion(`About ${stop.file} line ${n}: `)}
              />
            ) : (
              <p className="mute">Loading {stop.file}…</p>
            )}
            <Markdown text={stop.explanation} />
          </>
        )}
        <div className="row">
          <button disabled={index === 0} onClick={() => setIndex(index - 1)}>
            Previous
          </button>
          <button
            disabled={index === step.tour.stops.length - 1}
            onClick={() => setIndex(index + 1)}
          >
            Next
          </button>
          <button className="primary" disabled={go.busy} onClick={ready}>
            {go.busy ? 'Opening the interview…' : "I'm ready for the interview"}
          </button>
        </div>
        {go.error && <p className="error">{go.error}</p>}
      </section>
      <aside className="panel chat" aria-label="Ask the tutor">
        <h2>Ask about the code</h2>
        <p className="mute">Click a line number to ask about that line.</p>
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
        />
        <button disabled={chat.busy || !question.trim()} onClick={ask}>
          {chat.busy ? 'Asking…' : 'Ask'}
        </button>
        {chat.error && <p className="error">{chat.error}</p>}
      </aside>
    </div>
  )
}
