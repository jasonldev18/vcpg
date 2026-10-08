import type { Idea } from '../api/types'

type Data = Record<string, unknown>

function parse(json: string): Data {
  try {
    return JSON.parse(json) as Data
  } catch {
    return {}
  }
}

const str = (v: unknown) => (typeof v === 'string' ? v : '')

// Fixed templates filled with the generator's example content (DESIGN section 7).
export function Thumbnail({
  template,
  dataJson,
}: {
  template: Idea['thumbnail']['template']
  dataJson: string
}) {
  const d = parse(dataJson)
  if (template === 'chat')
    return (
      <div className="th th-chat" aria-hidden="true">
        <span className="bubble q">{str(d.question)}</span>
        <span className="bubble a">{str(d.answer)}</span>
        <span className="cite">{str(d.cite)}</span>
      </div>
    )
  if (template === 'ranked') {
    const items = Array.isArray(d.items) ? (d.items as { label?: string; score?: number }[]) : []
    return (
      <div className="th th-ranked" aria-hidden="true">
        <span className="cite">{str(d.query)}</span>
        {items.slice(0, 3).map((item, i) => (
          <div key={i} className="bar-row">
            <span>{item.label}</span>
            <span className="bar" style={{ width: `${Math.round((item.score ?? 0) * 100)}%` }} />
          </div>
        ))}
      </div>
    )
  }
  if (template === 'cluster') {
    const seed = typeof d.seed === 'number' ? d.seed : 7
    const dots = Array.from({ length: 18 }, (_, i) => {
      const a = (seed * 9301 + i * 49297) % 233280
      return { x: 10 + (a % 80), y: 10 + ((a * 7) % 60), near: i < 7 }
    })
    return (
      <svg className="th th-cluster" viewBox="0 0 100 80" aria-hidden="true">
        {dots.map((p, i) => (
          <circle
            key={i}
            cx={p.near ? 25 + (p.x % 25) : p.x}
            cy={p.near ? 25 + (p.y % 25) : p.y}
            r={2.2}
          />
        ))}
        <circle cx={38} cy={38} r={18} className="ring" />
        <text x={58} y={20}>
          {str(d.label)}
        </text>
      </svg>
    )
  }
  if (template === 'code_hits')
    return (
      <div className="th th-code" aria-hidden="true">
        {[60, 85, 40, 75, 55].map((w, i) => (
          <span
            key={i}
            className={i === 1 || i === 3 ? 'line hit' : 'line'}
            style={{ width: `${w}%` }}
          />
        ))}
        <span className="cite">{str(d.hit)}</span>
      </div>
    )
  if (template === 'chart') {
    const values = Array.isArray(d.values) ? (d.values as number[]).slice(0, 6) : []
    const max = Math.max(...values, 1)
    return (
      <div className="th th-chart" aria-hidden="true">
        {values.map((v, i) => (
          <span key={i} className="col" style={{ height: `${(v / max) * 100}%` }} />
        ))}
        <span className="cite">{str(d.label)}</span>
      </div>
    )
  }
  const blocks = Array.isArray(d.blocks) ? (d.blocks as string[]).slice(0, 5) : []
  return (
    <div className="th th-pipeline" aria-hidden="true">
      {blocks.map((b, i) => (
        <span key={i} className="block">
          {b}
        </span>
      ))}
    </div>
  )
}

const FAMILIARITY = { new: 'new', basics: 'know the basics', used: 'used it before' }
const DIFFICULTY = { gentle: 'Gentle', medium: 'Medium', stretch: 'Stretch' }

export function IdeaCardView({
  idea,
  expanded,
  onOpen,
  onBuild,
  onTeach,
  busy,
}: {
  idea: Idea
  expanded: boolean
  onOpen: () => void
  onBuild: () => void
  onTeach: () => void
  busy: boolean
}) {
  return (
    <article className={`panel idea${expanded ? ' expanded' : ''}`} aria-label={idea.name}>
      <button className="idea-head" onClick={onOpen} aria-expanded={expanded}>
        <Thumbnail template={idea.thumbnail.template} dataJson={idea.thumbnail.data_json} />
        <h2>{idea.name}</h2>
        <p>{idea.line}</p>
        <p className="mute">
          {DIFFICULTY[idea.difficulty]} · {idea.step_count} steps
        </p>
      </button>
      <p className="chips">
        {idea.concepts.map((c) => (
          <span key={c.name} className={`chip ${c.familiarity}`}>
            {c.name} <small>{FAMILIARITY[c.familiarity]}</small>
          </span>
        ))}
      </p>
      {expanded && (
        <div className="stack">
          <p>{idea.pitch}</p>
          <div className="arch-strip" aria-label="Architecture">
            {idea.architecture.map((a, i) => (
              <span key={i} className="block">
                {a}
              </span>
            ))}
          </div>
          <h3>What you will be asked</h3>
          <ul>
            {idea.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
          <div className="row">
            <button className="primary" disabled={busy} onClick={onBuild}>
              Build this
            </button>
            <button disabled={busy} onClick={onTeach}>
              Teach me first
            </button>
          </div>
        </div>
      )}
    </article>
  )
}
