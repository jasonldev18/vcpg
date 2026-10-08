import type { SlideData, Visual } from '../api/types'

const COLORS = ['var(--acc)', 'var(--acc3)', 'var(--acc2)', 'var(--you)', 'var(--pass)']

function Box({ x, y, w, label }: { x: number; y: number; w: number; label: string }) {
  return (
    <g>
      <rect x={x - w / 2} y={y - 18} width={w} height={36} rx={6} className="sv-box" />
      <text x={x} y={y + 4} textAnchor="middle" className="sv-label">
        {label.length > 22 ? `${label.slice(0, 21)}…` : label}
      </text>
    </g>
  )
}

function Arrow({
  x1,
  y1,
  x2,
  y2,
  label,
}: {
  x1: number
  y1: number
  x2: number
  y2: number
  label?: string
}) {
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} className="sv-edge" markerEnd="url(#sv-arrow)" />
      {label && (
        <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} textAnchor="middle" className="sv-small">
          {label}
        </text>
      )}
    </g>
  )
}

function Architecture({ spec }: { spec: Extract<Visual, { kind: 'architecture' }>['spec'] }) {
  const groups = [...new Set(spec.nodes.map((n) => n.group))]
  const w = Math.min(560 / groups.length, 150)
  const pos = new Map<string, [number, number]>()
  groups.forEach((g, gi) => {
    const members = spec.nodes.filter((n) => n.group === g)
    members.forEach((n, ni) =>
      pos.set(n.id, [((gi + 0.5) * 600) / groups.length, 60 + ((ni + 0.5) * 260) / members.length]),
    )
  })
  return (
    <>
      {groups.map((g, gi) => (
        <text
          key={g}
          x={((gi + 0.5) * 600) / groups.length}
          y={24}
          textAnchor="middle"
          className="sv-group"
        >
          {g.toUpperCase()}
        </text>
      ))}
      {spec.edges.map((e) => {
        const a = pos.get(e.from)
        const b = pos.get(e.to)
        if (!a || !b) return null
        const dir = b[0] >= a[0] ? 1 : -1
        const shift = a[0] === b[0] ? 0 : w / 2
        return (
          <Arrow
            key={`${e.from}-${e.to}`}
            x1={a[0] + dir * shift}
            y1={a[1]}
            x2={b[0] - dir * shift}
            y2={b[1]}
            label={e.label}
          />
        )
      })}
      {spec.nodes.map((n) => {
        const [x, y] = pos.get(n.id) ?? [0, 0]
        return <Box key={n.id} x={x} y={y} w={w} label={n.label} />
      })}
    </>
  )
}

function Flow({ steps }: { steps: string[] }) {
  const w = Math.min(520 / steps.length, 130)
  const xs = steps.map((_, i) => ((i + 0.5) * 600) / steps.length)
  return (
    <>
      {xs.slice(1).map((x, i) => (
        <Arrow key={i} x1={xs[i] + w / 2} y1={170} x2={x - w / 2} y2={170} />
      ))}
      {steps.map((s, i) => (
        <Box key={s} x={xs[i]} y={170} w={w} label={s} />
      ))}
    </>
  )
}

function Chart({ spec }: { spec: Extract<Visual, { kind: 'chart' }>['spec'] }) {
  const ys = spec.series.flatMap((s) => s.y)
  const max = Math.max(...ys, 0) || 1
  const n = Math.max(...spec.series.map((s) => s.x.length))
  const plot = (i: number) => 60 + ((i + 0.5) * 520) / n
  const height = (v: number) => (v / max) * 250
  return (
    <>
      <line x1={50} y1={300} x2={590} y2={300} className="sv-axis" />
      <line x1={50} y1={40} x2={50} y2={300} className="sv-axis" />
      {spec.series.map((s, si) =>
        spec.type === 'bar'
          ? s.y.map((v, i) => {
              const bw = 400 / n / spec.series.length
              return (
                <rect
                  key={`${si}-${i}`}
                  x={plot(i) - (bw * spec.series.length) / 2 + si * bw}
                  y={300 - height(v)}
                  width={bw}
                  height={height(v)}
                  fill={COLORS[si % COLORS.length]}
                />
              )
            })
          : s.y.map((v, i) => (
              <circle
                key={`${si}-${i}`}
                cx={plot(i)}
                cy={300 - height(v)}
                r={4}
                fill={COLORS[si % COLORS.length]}
              />
            )),
      )}
      {spec.series[0].x.map((x, i) => (
        <text key={i} x={plot(i)} y={318} textAnchor="middle" className="sv-small">
          {String(x)}
        </text>
      ))}
      <text x={320} y={338} textAnchor="middle" className="sv-small">
        {spec.x_label}
      </text>
      <text x={14} y={170} className="sv-small" transform="rotate(-90 14 170)" textAnchor="middle">
        {spec.y_label}
      </text>
    </>
  )
}

export function VisualView({ visual, code }: { visual: Visual; code: string[] | null }) {
  if (visual.kind === 'code') {
    const [start] = visual.spec.lines
    return (
      <pre className="code-view" aria-label={`Code from ${visual.spec.path}`}>
        <div className="mute">{visual.spec.path}</div>
        {(code ?? ['(code not found in the commit)']).map((line, i) => (
          <div key={i} className={visual.spec.highlight.includes(start + i) ? 'hl' : undefined}>
            <span className="line-no">{start + i}</span>
            <code>{line || ' '}</code>
          </div>
        ))}
      </pre>
    )
  }
  if (visual.kind === 'table')
    return (
      <table className="sv-table">
        <thead>
          <tr>
            {visual.spec.columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visual.spec.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    )
  return (
    <svg viewBox="0 0 600 340" className="sv" role="img" aria-label={`${visual.kind} diagram`}>
      <defs>
        <marker
          id="sv-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto"
        >
          <path d="M0,0 L10,5 L0,10 z" className="sv-arrowhead" />
        </marker>
      </defs>
      {visual.kind === 'architecture' && <Architecture spec={visual.spec} />}
      {visual.kind === 'flow' && <Flow steps={visual.spec.steps} />}
      {visual.kind === 'chart' && <Chart spec={visual.spec} />}
    </svg>
  )
}

export function SlideView({ entry }: { entry: { slide: SlideData; code: string[] | null } }) {
  const { slide } = entry
  return (
    <article className="slide" aria-label={`Slide: ${slide.title}`}>
      <p className="kicker">{slide.kicker}</p>
      <h2 className="slide-title">{slide.title}</h2>
      <p className="mute">{slide.what}</p>
      <div className="slide-body">
        <div className="slide-visual">
          <VisualView visual={slide.visual} code={entry.code} />
        </div>
        <div className="slide-side">
          {slide.decisions.length > 0 && (
            <>
              <h3>Decisions</h3>
              <ul>
                {slide.decisions.map((d) => (
                  <li key={d.choice}>
                    <strong>{d.choice}</strong>: {d.tradeoff}
                  </li>
                ))}
              </ul>
            </>
          )}
          {slide.failure_and_scale.length > 0 && (
            <>
              <h3>Failure and scale</h3>
              <ul>
                {slide.failure_and_scale.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
      {slide.struggled.length > 0 && (
        <footer className="slide-footer">
          Questions I struggled with:{' '}
          {slide.struggled.map((s) => `${s.question} (${s.hints} hints)`).join(' · ')}
        </footer>
      )}
    </article>
  )
}
