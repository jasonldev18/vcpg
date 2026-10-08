import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { api } from '../api/client'
import type { IdeaBatch, LessonPathView, Project } from '../api/types'
import { IdeaCardView } from '../components/IdeaCard'
import { useAction } from '../components/useAction'

type Path = 'plan' | 'ideas' | 'concept'

const USES = ['Answer questions', 'Rank or recommend', 'Find patterns', 'Search code']
const DATA = ['Files I upload', 'A public dataset', 'A folder on disk']

function Chips({
  options,
  value,
  onChange,
  label,
}: {
  options: string[]
  value: string
  onChange: (v: string) => void
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="chips">
      <span className="mute">{label}</span>
      {options.map((o) => (
        <button
          key={o}
          className={`chip${value === o ? ' current' : ''}`}
          aria-pressed={value === o}
          onClick={() => onChange(value === o ? '' : o)}
        >
          {o}
        </button>
      ))}
    </div>
  )
}

export function Start() {
  const [params] = useSearchParams()
  const [path, setPath] = useState<Path>(params.get('idea') ? 'ideas' : 'plan')
  const [brief, setBrief] = useState('')
  const [topic, setTopic] = useState('')
  const [use, setUse] = useState('')
  const [data, setData] = useState('')
  const [concept, setConcept] = useState('')
  const [batch, setBatch] = useState<IdeaBatch | null>(null)
  const [open, setOpen] = useState<number | null>(
    params.get('card') ? Number(params.get('card')) : null,
  )
  const { busy, error, run } = useAction()
  const navigate = useNavigate()

  useEffect(() => {
    const id = params.get('idea')
    if (id) void api.get<IdeaBatch>(`/api/ideas/${id}`).then(setBatch) // back from "Teach me first"
  }, [params])

  const plan = async () => {
    if (await run(() => api.post<Project>('/api/projects', { brief }))) navigate('/')
  }
  const ideas = () =>
    run(() => api.post<IdeaBatch>('/api/ideas', { topic, use, data })).then((b) => b && setBatch(b))
  const teachConcept = async () => {
    const p = await run(() => api.post<LessonPathView>('/api/lessons', { concept }))
    if (p) navigate(`/lesson/${p.id}`)
  }
  const build = async (card: number) => {
    if (batch && (await run(() => api.post<Project>(`/api/ideas/${batch.id}/build`, { card }))))
      navigate('/')
  }
  const teach = async (card: number) => {
    const p =
      batch && (await run(() => api.post<LessonPathView>(`/api/ideas/${batch.id}/teach`, { card })))
    if (p) navigate(`/lesson/${p.id}`)
  }

  const tab = (value: Path, title: string, line: string) => (
    <button
      className={`panel path-card${path === value ? ' current' : ''}`}
      aria-pressed={path === value}
      onClick={() => setPath(value)}
    >
      <h2>{title}</h2>
      <p className="mute">{line}</p>
    </button>
  )

  return (
    <div className="stack start">
      <h1>Start a project</h1>
      <div className="paths">
        {tab('plan', 'I have a plan', 'Describe what you want to build.')}
        {tab('ideas', 'Give me ideas', 'Pick a topic, get four projects.')}
        {tab('concept', 'Teach me a concept', 'Learn it from zero first.')}
      </div>
      {path === 'plan' && (
        <section className="panel stack">
          <label className="field">
            <span>What do you want to build? Goal, rough features, any stack preferences.</span>
            <textarea
              rows={8}
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              placeholder="A movie recommender that suggests five films from my MovieLens ratings…"
            />
          </label>
          <button className="primary" disabled={busy || !brief.trim()} onClick={plan}>
            {busy ? 'The planner is drafting…' : 'Plan it'}
          </button>
        </section>
      )}
      {path === 'ideas' && (
        <section className="panel stack">
          <label className="field">
            <span>Topic</span>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="RAG and vectors"
            />
          </label>
          <Chips label="How do you want to use it?" options={USES} value={use} onChange={setUse} />
          <Chips
            label="Where does the data come from?"
            options={DATA}
            value={data}
            onChange={setData}
          />
          <button className="primary" disabled={busy || !topic.trim()} onClick={ideas}>
            {busy ? 'Thinking up ideas…' : 'Give me ideas'}
          </button>
        </section>
      )}
      {path === 'ideas' && batch && (
        <div className="ideas">
          {batch.cards.map((idea, i) => (
            <IdeaCardView
              key={i}
              idea={idea}
              expanded={open === i}
              busy={busy}
              onOpen={() => setOpen(open === i ? null : i)}
              onBuild={() => build(i)}
              onTeach={() => teach(i)}
            />
          ))}
        </div>
      )}
      {path === 'concept' && (
        <section className="panel stack">
          <label className="field">
            <span>Which concept?</span>
            <input
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder="cosine similarity"
            />
          </label>
          <button className="primary" disabled={busy || !concept.trim()} onClick={teachConcept}>
            {busy ? 'Building your lesson path…' : 'Teach me'}
          </button>
        </section>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
