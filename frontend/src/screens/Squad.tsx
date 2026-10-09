import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { SquadMember } from '../api/types'
import { useAction } from '../components/useAction'
import { useFrame, useReducedMotion } from '../scenes/canvas'
import { CREW, drawSprite } from '../scenes/sprites'
import { CODES, drawSuit, LOOKS, type AuditId } from '../scenes/suits'

type Crew = 'build_crew' | 'audit_crew' | 'helpers'
type ModelId = SquadMember['model']
type Effort = SquadMember['effort']

const MODELS: Record<ModelId, { name: string; short: string; speed: number; depth: number; note: string }> = {
  'claude-haiku-5-5': { name: 'Haiku 5.5', short: 'Haiku', speed: 9, depth: 4, note: 'Fastest. Built for routing, extraction and short summaries.' },
  'claude-sonnet-5-5': { name: 'Sonnet 5.5', short: 'Sonnet', speed: 7, depth: 7, note: 'Balanced speed and intelligence for teaching and chat.' },
  'claude-opus-5-5': { name: 'Opus 5.5', short: 'Opus', speed: 5, depth: 9, note: 'Deepest reasoning. Long agentic coding and judgment calls.' },
} // prettier-ignore
const EFFORTS: Effort[] = ['medium', 'high', 'xhigh', 'max'] // never low (CLAUDE.md)
const EFFORT_NOTE: Record<Effort, string> = {
  medium: 'Balanced. Good default for chat and well-scoped work.',
  high: 'Thinks as much as the task needs. Good for hard reasoning and code.',
  xhigh: 'Extended effort for long, multi-step agent runs.',
  max: 'No limit on thinking. Use only where it measurably helps.',
}

interface Card {
  title: string
  desc: string
  quote: string
  tools: string[]
  color: string
}

// Wording from Squad.dc.html; helpers are described from AGENTS.md.
const CARDS: Record<string, Card> = {
  planner: { title: 'Planner', desc: 'Turns your idea into a step-by-step plan and decides which modules this project needs.', quote: '"No step without a reason."', tools: ['Read project brief', 'Write step plan', 'Pick modules'], color: '#5AA9FF' },
  tutor: { title: 'Tutor', desc: 'Teaches the plan before any code exists, then walks you through the real code after review.', quote: '"If you can\'t explain it, you don\'t own it."', tools: ['Read plan and diff', 'Draw diagrams', 'Answer questions'], color: '#6FD98A' },
  builder: { title: 'Builder', desc: 'Writes the code for each step, lean and readable, and only inside the project folder.', quote: '"Thirty clean lines beat fifty clever ones."', tools: ['Edit files', 'Run commands in the sandbox'], color: '#FF9A52' },
  reviewer: { title: 'Reviewer', desc: 'Runs the tests and cuts any edge case it cannot prove is reachable.', quote: '"Prove that branch runs, or it goes."', tools: ['Run tests in sandbox', 'Remove dead code'], color: '#B58CFF' },
  interviewer: { title: 'Interviewer', desc: 'Asks the gate questions and digs into whatever the grader says is still missing.', quote: '"Walk me through why."', tools: ['Read rubric gaps', 'Ask follow-ups'], color: '#FF7EB6' },
  grader: { title: 'Grader', desc: 'Silently scores each answer against the hidden rubric; code decides whether the gate opens.', quote: '"Show me the sentence."', tools: ['Score against rubric', 'Quote evidence'], color: '#41D6C3' },
  slide_writer: { title: 'Slide writer', desc: 'Turns each passed step into an interview slide with the decisions and failure modes.', quote: '"One slide, one story."', tools: ['Summarize step', 'Build slide'], color: '#FFD45E' },
  rook: { title: 'Rook', desc: 'Audit lead. Traces issues across agents and writes the fixes worth a pull request.', quote: '"Find the cause, not the symptom."', tools: ['Read all reports', 'Trace causes', 'Propose fixes'], color: '#FF4D5E' },
  bolt: { title: 'Bolt', desc: 'Build auditor. Checks plans, code quality and whether the reviewer cut anything it should not have.', quote: '"Measure twice, commit once."', tools: ['Read plans and code', 'Check reviewer cuts'], color: '#5AA9FF' },
  echo: { title: 'Echo', desc: 'Teaching auditor. Checks lessons, interview questions, hints and grader calibration.', quote: '"Was that a hint or the answer?"', tools: ['Read transcripts', 'Check calibration'], color: '#41D6C3' },
  pixel: { title: 'Pixel', desc: 'Output auditor. Checks slides, READMEs and dossiers against what the code actually does.', quote: '"The deck has to match the diff."', tools: ['Compare slides to code', 'Check README claims'], color: '#FFD45E' },
  lesson_builder: { title: 'Lesson builder', desc: 'Builds lesson paths from source passages; every sentence cites a trusted source.', quote: '"Cite it or cut it."', tools: ['Read retrieved passages', 'Write lessons and questions'], color: '#BFA58F' },
  idea_generator: { title: 'Idea generator', desc: 'Proposes four buildable projects for a topic, each with a picture of it in use.', quote: '"Small enough to finish, real enough to defend."', tools: ['Read your history', 'Draft idea cards'], color: '#BFA58F' },
  readme_coach: { title: 'README coach', desc: 'Prepares a README template and checks every claim you write against the project.', quote: '"Point, explain, never rewrite."', tools: ['Read the project', 'Flag mismatches'], color: '#BFA58F' },
  dossier_writer: { title: 'Dossier writer', desc: 'Compresses a finished project into a short dossier for mock interviews.', quote: '"Every number from the record."', tools: ['Read slides and gates', 'Write the dossier'], color: '#BFA58F' },
} // prettier-ignore

const CREWS: { id: Crew; label: string; note: string }[] = [
  {
    id: 'build_crew',
    label: 'Build crew',
    note: 'Seven agents that teach, build and gate each step.',
  },
  {
    id: 'audit_crew',
    label: 'Audit crew',
    note: 'Four agents that audit the app after projects and every two weeks.',
  },
  {
    id: 'helpers',
    label: 'Helpers',
    note: 'Agents behind lessons, ideas, the README coach and dossiers.',
  },
]

function Bars({ value, color }: { value: number; color: string }) {
  const filled = Math.round(Math.max(1, Math.min(10, value)))
  return (
    <div className="segs" aria-hidden="true">
      {Array.from({ length: 10 }, (_, i) => (
        <div key={i} className="seg" style={{ background: i < filled ? color : undefined }} />
      ))}
    </div>
  )
}

function Portrait({ agent }: { agent: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const still = useReducedMotion()
  const draw = useCallback(
    (now: number) => {
      const c = canvas.current
      const g = c?.getContext('2d')
      if (!c || !g) return
      const W = 380
      const H = 440
      const t = still ? 0 : now / 1000
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      if (c.width !== W * dpr) {
        c.width = W * dpr
        c.height = H * dpr
      }
      g.setTransform(dpr, 0, 0, dpr, 0, 0)
      g.imageSmoothingEnabled = false
      const bg = g.createLinearGradient(0, 0, 0, H)
      bg.addColorStop(0, '#1A0F0A')
      bg.addColorStop(1, '#2A140E')
      g.fillStyle = bg
      g.fillRect(0, 0, W, H)
      g.strokeStyle = 'rgba(255,155,61,0.08)'
      for (let i = 0; i < 12; i++) {
        g.beginPath()
        g.moveTo(190, 250)
        g.lineTo(i * 36 - 20, H)
        g.stroke()
      }
      g.globalCompositeOperation = 'lighter'
      const glow = g.createRadialGradient(190, 200, 10, 190, 200, 200)
      glow.addColorStop(0, 'rgba(255,155,61,0.35)')
      glow.addColorStop(1, 'rgba(255,155,61,0)')
      g.fillStyle = glow
      g.fillRect(0, 0, W, H)
      for (let i = 0; i < 48; i++) {
        if (i % 4 === 3) continue
        const an = (i / 48) * Math.PI * 2 + t * 0.4
        g.fillStyle = 'rgba(255,210,122,0.6)'
        g.fillRect(Math.round(190 + Math.cos(an) * 120), Math.round(372 + Math.sin(an) * 22), 2, 2)
      }
      g.fillStyle = 'rgba(255,155,61,0.25)'
      g.beginPath()
      g.ellipse(190, 372, 92, 15, 0, 0, Math.PI * 2)
      g.fill()
      g.globalCompositeOperation = 'source-over'
      const sprite = CREW.find((a) => a.id === agent)
      if (sprite) {
        const size = 18
        const bob = (Math.floor(t * 1.6) % 2) * 4
        drawSprite(
          g,
          sprite,
          190 - 6 * size,
          372 - 12 * size - 4 - bob,
          size,
          t % 3.6 < 0.14,
          '#FF9B3D',
        )
      } else if (agent in LOOKS) {
        drawSuit(g, agent as AuditId, 190, 372, 10.6, t)
      }
      g.fillStyle = CARDS[agent].color
      g.fillRect(0, 0, W, 3)
    },
    [agent, still],
  )
  useFrame(draw, still)
  if (!CREW.some((a) => a.id === agent) && !(agent in LOOKS)) return null
  return (
    <canvas
      ref={canvas}
      className="portrait"
      role="img"
      aria-label={`${CARDS[agent].title}, pixel portrait`}
    />
  )
}

export function Squad() {
  const [saved, setSaved] = useState<SquadMember[] | null>(null)
  const [draft, setDraft] = useState<Record<string, { model: ModelId; effort: Effort }>>({})
  const [crew, setCrew] = useState<Crew>('build_crew')
  const [selected, setSelected] = useState('planner')
  const [note, setNote] = useState<string | null>(null)
  const { busy, error, run } = useAction()

  useEffect(() => {
    void api.get<SquadMember[]>('/api/squad').then((list) => {
      setSaved(list)
      setDraft(Object.fromEntries(list.map((a) => [a.agent, { model: a.model, effort: a.effort }])))
    })
  }, [])

  if (!saved) return <p className="mute">Loading…</p>
  const members = saved.filter((a) => a.group === crew)
  const sel = saved.find((a) => a.agent === selected) ?? members[0]
  const cur = draft[sel.agent]
  const card = CARDS[sel.agent]
  const custom = (a: SquadMember) => {
    const d = draft[a.agent]
    return d.model !== a.recommended.model || d.effort !== a.recommended.effort
  }
  const pick = (change: Partial<{ model: ModelId; effort: Effort }>) => {
    setDraft({ ...draft, [sel.agent]: { ...cur, ...change } })
    setNote(null)
  }
  const save = async () => {
    const agents = saved.map((a) => ({ agent: a.agent, ...draft[a.agent] }))
    const list = await run(() => api.put<SquadMember[]>('/api/squad', { agents }))
    if (list) {
      setSaved(list)
      setNote('Loadout saved. It applies to the next call.')
    }
  }
  const effortIndex = EFFORTS.indexOf(cur.effort)
  const model = MODELS[cur.model]

  return (
    <div className="stack">
      <header className="row wrap">
        <h1 className="pix squad-heading">Squad loadout</h1>
        <span className="disp small mute">Choose each agent's model and how hard it thinks</span>
      </header>
      <div className="squad">
        <section className="frame stack" aria-label="Agents">
          <div className="row wrap">
            {CREWS.map((c) => (
              <button
                key={c.id}
                className={`tab${crew === c.id ? ' on' : ''}`}
                aria-pressed={crew === c.id}
                onClick={() => {
                  setCrew(c.id)
                  setSelected(saved.find((a) => a.group === c.id)?.agent ?? '')
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
          <span className="mono mute">{CREWS.find((c) => c.id === crew)?.note}</span>
          {members.map((a) => (
            <button
              key={a.agent}
              className={`agent-row${a.agent === sel.agent ? ' on' : ''}`}
              aria-pressed={a.agent === sel.agent}
              onClick={() => setSelected(a.agent)}
            >
              <span className="hex" style={{ background: CARDS[a.agent].color }}>
                {CARDS[a.agent].title.charAt(0)}
              </span>
              <span className="stack tight">
                <span className="disp agent-name">{CARDS[a.agent].title}</span>
                <span className="row wrap tight">
                  <span className="pill" style={{ color: CARDS[a.agent].color }}>
                    {MODELS[draft[a.agent].model].short}
                  </span>
                  <span className="pill mute">{draft[a.agent].effort}</span>
                  <span className={`pill ${custom(a) ? 'custom' : 'mute'}`}>
                    {custom(a) ? 'custom' : 'recommended'}
                  </span>
                </span>
              </span>
            </button>
          ))}
        </section>

        <section className="frame stack" aria-label={`${card.title} loadout`}>
          <span className="disp small" style={{ color: card.color }}>
            {CREWS.find((c) => c.id === sel.group)?.label} · runs on{' '}
            {sel.runtime === 'agent_sdk' ? 'Agent SDK' : 'API'}
          </span>
          <h2 className="squad-title">{card.title}</h2>
          <p>{card.desc}</p>
          <p className="mute quote">{card.quote}</p>

          <h2>Model</h2>
          <div className="row wrap">
            {(Object.keys(MODELS) as ModelId[]).map((m) => (
              <button
                key={m}
                className={`mcard${cur.model === m ? ' on' : ''}`}
                aria-pressed={cur.model === m}
                onClick={() => pick({ model: m })}
              >
                <span className="row spread">
                  <span className="disp">{MODELS[m].name}</span>
                  {sel.recommended.model === m && <span className="mono rec">recommended</span>}
                </span>
                <span className="mute">{MODELS[m].note}</span>
              </button>
            ))}
          </div>

          <h2>Effort</h2>
          <div className="row wrap">
            {EFFORTS.map((e) => (
              <button
                key={e}
                className={`eff${cur.effort === e ? ' on' : ''}`}
                aria-pressed={cur.effort === e}
                onClick={() => pick({ effort: e })}
              >
                {e}
              </button>
            ))}
          </div>
          <p className="mute">{EFFORT_NOTE[cur.effort]}</p>

          <h2>Relative profile</h2>
          <div
            className="profile"
            role="img"
            aria-label={`Relative depth ${Math.round(model.depth + effortIndex * 0.6)} of 10, speed ${Math.round(model.speed - effortIndex * 1.1)} of 10`}
          >
            <span className="disp small mute">Depth</span>
            <Bars value={model.depth + effortIndex * 0.6} color="var(--acc3)" />
            <span className="disp small mute">Speed</span>
            <Bars value={model.speed - effortIndex * 1.1} color="var(--you)" />
          </div>

          <h2>Tools</h2>
          <div className="row wrap">
            {card.tools.map((t) => (
              <span key={t} className="mono tool">
                {t}
              </span>
            ))}
          </div>

          <div className="row wrap">
            <button className="primary" disabled={busy} onClick={save}>
              Save loadout
            </button>
            <button onClick={() => pick(sel.recommended)}>Reset to recommended</button>
            <span className="mono mute small">
              Recommended: {MODELS[sel.recommended.model].name} / {sel.recommended.effort}
            </span>
          </div>
          {note && !error && <p className="ok">{note}</p>}
          {error && <p className="error">{error}</p>}
        </section>

        <section className="frame stack portrait-frame" aria-label="Portrait">
          <Portrait agent={sel.agent} />
          <div className="badge">
            <span className="pix badge-num" style={{ color: card.color, borderColor: card.color }}>
              {sel.agent in CODES
                ? CODES[sel.agent as AuditId].slice(-3)
                : String(members.indexOf(sel) + 1).padStart(2, '0')}
            </span>
            <span
              className="disp badge-name"
              style={{ background: `linear-gradient(90deg, ${card.color}, rgba(255,155,61,.25))` }}
            >
              {card.title}
            </span>
          </div>
          <div className="facts">
            <div>
              <span className="disp small mute">Model</span>
              <span className="mono">{model.name}</span>
            </div>
            <div>
              <span className="disp small mute">Effort</span>
              <span className="mono">{cur.effort}</span>
            </div>
            <div>
              <span className="disp small mute">Runs on</span>
              <span className="mono">{sel.runtime === 'agent_sdk' ? 'Agent SDK' : 'API'}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
