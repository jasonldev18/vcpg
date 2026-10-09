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

// The cluster thumbnail's dot layout and colours, from Ideas.dc.html.
const DOTS = [[14, 30], [22, 22], [26, 40], [18, 46], [30, 28], [62, 20], [70, 30], [66, 44], [76, 22], [44, 70], [52, 78], [40, 82], [56, 66], [84, 70]] // prettier-ignore
const dotColour = (i: number) =>
  i < 5 ? 'var(--acc3)' : i < 9 ? 'var(--acc)' : i < 13 ? 'var(--acc2)' : '#8a7260'
const CODE_LINES = [70, 92, 84, 60, 78, 50]

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
      <span className="th th-chat" aria-hidden="true">
        <span className="bub q">{str(d.question)}</span>
        <span className="bub a">{str(d.answer)}</span>
        <span className="bub cite">{str(d.cite)}</span>
      </span>
    )
  if (template === 'ranked') {
    const items = Array.isArray(d.items) ? (d.items as { label?: string; score?: number }[]) : []
    return (
      <span className="th th-ranked" aria-hidden="true">
        <span className="bub query">{str(d.query)}</span>
        <span className="rows">
          {items.slice(0, 3).map((item, i) => (
            <span key={i} className="bar-row">
              <span className="label">{item.label}</span>
              <span className="bar" style={{ width: `${Math.round((item.score ?? 0) * 60)}%` }} />
            </span>
          ))}
        </span>
      </span>
    )
  }
  if (template === 'cluster')
    return (
      <span className="th th-cluster" aria-hidden="true">
        {DOTS.map(([x, y], i) => (
          <span
            key={i}
            className="dot"
            style={{ left: `${x}%`, top: `${y}%`, background: dotColour(i) }}
          />
        ))}
        <span className="ring" />
        <span className="bub label">{str(d.label)}</span>
      </span>
    )
  if (template === 'code_hits')
    return (
      <span className="th th-code" aria-hidden="true">
        <span className="lines">
          {CODE_LINES.map((w, i) => (
            <span
              key={i}
              className={i === 2 || i === 3 ? 'line hit' : 'line'}
              style={{ width: `${w}%` }}
            />
          ))}
        </span>
        <span className="bub cite">{str(d.hit)}</span>
      </span>
    )
  if (template === 'chart') {
    const values = Array.isArray(d.values) ? (d.values as number[]).slice(0, 6) : []
    const max = Math.max(...values, 1)
    return (
      <span className="th th-chart" aria-hidden="true">
        <span className="cols">
          {values.map((v, i) => (
            <span key={i} className="col" style={{ height: `${(v / max) * 100}%` }} />
          ))}
        </span>
        <span className="bub label">{str(d.label)}</span>
      </span>
    )
  }
  const blocks = Array.isArray(d.blocks) ? (d.blocks as string[]).slice(0, 4) : []
  return (
    <span className="th th-pipeline" aria-hidden="true">
      {blocks.map((b, i) => (
        <span key={i} className="step">
          {i > 0 && (
            <span className="wire">
              <i />
            </span>
          )}
          <span className="box">{b}</span>
        </span>
      ))}
    </span>
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
