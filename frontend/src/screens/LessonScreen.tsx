import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '../api/client'
import type {
  LessonContent,
  LessonPathView,
  LessonQuestion,
  LessonSection,
  SourceRow,
  Visual,
} from '../api/types'
import { Markdown } from '../components/Markdown'
import { VisualView } from '../components/SlideView'
import { useAction } from '../components/useAction'

const TITLES: Record<LessonSection['kind'], string> = {
  start_here: 'Start here',
  see_it: 'See it',
  worked_example: 'Worked example',
  check_yourself: 'Check yourself',
  your_turn: 'Your turn',
  recap: 'Recap',
}

function parseVisual(json: string): Visual | null {
  try {
    return json ? (JSON.parse(json) as Visual) : null
  } catch {
    return null
  }
}

function Choice({ q }: { q: LessonQuestion }) {
  const [picked, setPicked] = useState<number | null>(null)
  const option = picked === null ? null : q.options[picked]
  return (
    <div className="question">
      <p>{q.prompt}</p>
      <div className="row wrap">
        {q.options.map((o, i) => (
          <button
            key={i}
            aria-pressed={picked === i}
            className={picked === i ? (o.correct ? 'right' : 'wrong') : undefined}
            onClick={() => setPicked(i)}
          >
            {o.text}
          </button>
        ))}
      </div>
      {option && (
        <p className={option.correct ? 'ok' : 'error'}>
          {option.correct ? 'Correct. ' : 'Not quite. '}
          {option.why}
        </p>
      )}
    </div>
  )
}

function Written({
  q,
  onAnswer,
}: {
  q: LessonQuestion
  onAnswer: (text: string) => Promise<Record<string, unknown> | undefined>
}) {
  const [text, setText] = useState(q.type === 'code' ? q.answer : '')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    setResult((await onAnswer(text)) ?? null)
    setBusy(false)
  }
  return (
    <div className="question">
      <p>{q.prompt}</p>
      <textarea
        className={q.type === 'code' ? 'you code-input' : 'you'}
        aria-label="Your answer"
        rows={q.type === 'code' ? 8 : 4}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button disabled={busy || !text.trim()} onClick={submit}>
        {busy ? 'Checking…' : q.type === 'code' ? 'Run the tests' : 'Check my answer'}
      </button>
      {result && q.type === 'short' && (
        <p aria-live="polite">
          {String(result.covered)} of {String(result.total)} points covered.{' '}
          {String(result.feedback ?? '')}
        </p>
      )}
      {result && q.type === 'code' && (
        <>
          <p className={result.passed ? 'ok' : 'error'}>
            {result.passed ? 'All tests pass.' : 'Some tests fail.'}
          </p>
          <pre className="code-view">{String(result.output)}</pre>
        </>
      )}
    </div>
  )
}

function Section({
  section,
  passages,
  onCite,
  onAnswer,
}: {
  section: LessonSection
  passages: string[]
  onCite: (id: string) => void
  onAnswer: (number: number, text: string) => Promise<Record<string, unknown> | undefined>
}) {
  const visual = parseVisual(section.visual_json)
  return (
    <section className="panel stack lesson-section" aria-label={TITLES[section.kind]}>
      <h2>{TITLES[section.kind]}</h2>
      {section.paragraphs.map((p, i) => (
        <p key={i}>
          {p.text}{' '}
          {p.citations.map((id) => (
            <button
              key={id}
              className="cite-chip"
              aria-label={`Source ${passages.indexOf(id) + 1}`}
              onClick={() => onCite(id)}
            >
              {passages.indexOf(id) + 1}
            </button>
          ))}
        </p>
      ))}
      {visual && <VisualView visual={visual} code={null} />}
      {section.code && <Markdown text={'```python\n' + section.code + '\n```'} />}
      {section.questions.map((q, i) =>
        q.type === 'mc' || q.type === 'tf' ? (
          <Choice key={i} q={q} />
        ) : (
          <Written key={i} q={q} onAnswer={(text) => onAnswer(i, text)} />
        ),
      )}
    </section>
  )
}

function Sources() {
  const [list, setList] = useState<SourceRow[]>([])
  const [url, setUrl] = useState('')
  const [kind, setKind] = useState<'trusted' | 'community'>('trusted')
  const { busy, error, run } = useAction()
  useEffect(() => {
    void api.get<SourceRow[]>('/api/sources').then(setList)
  }, [])
  const upload = async (file: File) => {
    const added = await run(() =>
      api.upload<SourceRow[]>(
        `/api/sources/upload?filename=${encodeURIComponent(file.name)}&kind=${kind}`,
        file,
      ),
    )
    if (added) setList(added)
  }
  return (
    <section className="panel stack" aria-label="Sources">
      <h2>Sources</h2>
      <p className="mute">Trusted sources back every claim. Community sources only add examples.</p>
      <select
        aria-label="Source kind"
        value={kind}
        onChange={(e) => setKind(e.target.value as 'trusted' | 'community')}
      >
        <option value="trusted">Trusted (books, papers, docs)</option>
        <option value="community">Community (posts, forums)</option>
      </select>
      <input
        aria-label="Source link"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://…"
      />
      <button
        disabled={busy || !url.trim()}
        onClick={() =>
          run(() => api.post<SourceRow[]>('/api/sources/url', { url, kind })).then(
            (l) => l && setList(l),
          )
        }
      >
        Add link
      </button>
      <input
        type="file"
        aria-label="Upload a PDF or markdown file"
        accept=".pdf,.md,.markdown,.txt"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <ul>
        {list.map((s) => (
          <li key={s.id}>
            {s.title}{' '}
            <span className="mute">
              ({s.kind}, {s.passages} passages)
            </span>
          </li>
        ))}
      </ul>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function LessonList() {
  const [paths, setPaths] = useState<{ id: number; concept: string; status: string }[]>([])
  useEffect(() => {
    void api.get<{ id: number; concept: string; status: string }[]>('/api/lessons').then(setPaths)
  }, [])
  return (
    <div className="lesson-layout">
      <section className="panel stack">
        <h1>Concept lesson</h1>
        <p className="mute">
          Start a new lesson path from <Link to="/start">Start a project</Link>, under Teach me a
          concept.
        </p>
        <ul>
          {paths.map((p) => (
            <li key={p.id}>
              <Link to={`/lesson/${p.id}`}>{p.concept}</Link>{' '}
              <span className="mute">({p.status})</span>
            </li>
          ))}
        </ul>
      </section>
      <Sources />
    </div>
  )
}

export function LessonScreen() {
  const { id } = useParams()
  const [path, setPath] = useState<LessonPathView | null>(null)
  const [index, setIndex] = useState(0)
  const [cited, setCited] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const { busy, error, run } = useAction()
  const requested = useRef<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (id) void api.get<LessonPathView>(`/api/lessons/${id}`).then(setPath)
  }, [id])

  const current = path?.lessons[index]
  useEffect(() => {
    const key = `${id}:${index}:${attempt}`
    if (!path || !current || current.content || requested.current === key) return
    requested.current = key
    void run(() => api.post<LessonPathView>(`/api/lessons/${path.id}/build/${index}`)).then(
      (p) => p && setPath(p),
    )
  }, [id, index, attempt, path, current, run])

  if (!id) return <LessonList />
  if (!path || !current) return <p className="mute">Loading…</p>

  const content: LessonContent | null = current.content
  const passageIds = Object.keys(current.passages ?? {})
  const answer = (kind: LessonSection['kind']) => (number: number, text: string) =>
    run(() =>
      api.post<Record<string, unknown>>(`/api/lessons/${path.id}/answer`, {
        lesson: index,
        section: kind,
        question: number,
        answer: text,
      }),
    )
  const passage = cited ? current.passages?.[cited] : null

  return (
    <div className="lesson-layout">
      <nav className="panel lesson-rail" aria-label="Lesson path">
        <p className="kicker">Lesson path</p>
        <h1>{path.concept}</h1>
        <ol>
          {path.lessons.map((l, i) => (
            <li key={i}>
              <button className={i === index ? 'current' : undefined} onClick={() => setIndex(i)}>
                {l.title} {l.content ? '' : <small>(not opened yet)</small>}
              </button>
            </li>
          ))}
        </ol>
        {path.return_idea_id !== null && (
          <button
            className="primary"
            onClick={() => navigate(`/start?idea=${path.return_idea_id}&card=${path.return_card}`)}
          >
            Back to the idea
          </button>
        )}
      </nav>
      <div className="stack">
        <section className="panel stack">
          <p className="kicker">
            Lesson {index + 1} of {path.lessons.length}
          </p>
          <h1>{current.title}</h1>
          <p className="mute">{current.goal}</p>
          {!content && (
            <p aria-live="polite">
              {error ? '' : 'The tutor is writing this lesson from its sources…'}
            </p>
          )}
          {content && content.by_the_end.length > 0 && (
            <>
              <h2>By the end you can</h2>
              <ul>
                {content.by_the_end.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </>
          )}
          {error && (
            <p className="error">
              {error} <button onClick={() => setAttempt((a) => a + 1)}>Try again</button>
            </p>
          )}
        </section>
        {content?.sections.map((s) => (
          <Section
            key={s.kind}
            section={s}
            passages={passageIds}
            onCite={setCited}
            onAnswer={answer(s.kind)}
          />
        ))}
        {current.dropped.length > 0 && (
          <p className="warning">
            {current.dropped.map((k) => TITLES[k]).join(', ')}: {path.dropped_note}
          </p>
        )}
        {content && content.community.length > 0 && (
          <section className="panel stack community" aria-label="Community">
            <h2>Community</h2>
            <p className="mute">
              How people use this in practice. These notes are examples, not sources.
            </p>
            <ul>
              {content.community.map((n, i) => (
                <li key={i}>{n.text}</li>
              ))}
            </ul>
          </section>
        )}
        {busy && <p className="mute">Working…</p>}
      </div>
      <aside className="panel stack" aria-label="Cited passage">
        <h2>Source</h2>
        {passage ? (
          <>
            <p className="kicker">
              {passageIds.indexOf(cited ?? '') + 1}. {passage.title}
            </p>
            <p>{passage.text}</p>
          </>
        ) : (
          <p className="mute">Click a numbered chip to read the passage behind a sentence.</p>
        )}
      </aside>
    </div>
  )
}
