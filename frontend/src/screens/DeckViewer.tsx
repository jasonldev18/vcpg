import { useEffect, useState } from 'react'
import { api, API_BASE } from '../api/client'
import type { Deck, Project, SlideData } from '../api/types'
import { SlideView } from '../components/SlideView'
import { useAction } from '../components/useAction'

function Editor({ slide, onSave }: { slide: SlideData; onSave: (s: SlideData) => void }) {
  const [draft, setDraft] = useState(slide)
  const field = (key: 'title' | 'what' | 'notes', label: string, rows = 1) => (
    <label className="field">
      <span>{label}</span>
      <textarea
        rows={rows}
        value={draft[key]}
        onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
      />
    </label>
  )
  return (
    <div className="stack">
      {field('title', 'Title')}
      {field('what', 'What it does', 2)}
      {draft.decisions.map((d, i) => (
        <label key={i} className="field">
          <span>Decision {i + 1}</span>
          <textarea
            rows={2}
            value={`${d.choice}: ${d.tradeoff}`}
            onChange={(e) => {
              const [choice, ...rest] = e.target.value.split(':')
              const decisions = draft.decisions.map((x, j) =>
                j === i ? { choice: choice.trim(), tradeoff: rest.join(':').trim() } : x,
              )
              setDraft({ ...draft, decisions })
            }}
          />
        </label>
      ))}
      {field('notes', 'Speaker notes', 5)}
      <button className="primary" onClick={() => onSave(draft)}>
        Save slide
      </button>
    </div>
  )
}

export function DeckViewer() {
  const [project, setProject] = useState<Project | null | undefined>(undefined)
  const [deck, setDeck] = useState<Deck | null>(null)
  const [index, setIndex] = useState(0)
  const [editing, setEditing] = useState(false)
  const [instruction, setInstruction] = useState('')
  const { busy, error, run } = useAction()

  useEffect(() => {
    void api.get<Project | null>('/api/projects/current').then(async (p) => {
      setProject(p)
      if (p) setDeck(await api.get<Deck>(`/api/projects/${p.id}/deck`))
    })
  }, [])

  if (project === undefined) return <p className="mute">Loading…</p>
  if (!project || !deck || deck.slides.length === 0)
    return (
      <section className="panel stack">
        <h1>Deck viewer</h1>
        <p className="mute">Slides appear here as each step passes its gate.</p>
      </section>
    )

  const base = `/api/projects/${project.id}`
  const current = deck.slides[Math.min(index, deck.slides.length - 1)]
  const reload = () => api.get<Deck>(`${base}/deck`).then(setDeck)
  const move = (by: number) => {
    const ids = deck.slides.map((s) => s.id)
    const i = ids.indexOf(current.id)
    ;[ids[i], ids[i + by]] = [ids[i + by], ids[i]]
    void run(() => api.post<Deck>(`${base}/deck/order`, { slide_ids: ids })).then((d) => {
      if (d) {
        setDeck(d)
        setIndex(i + by)
      }
    })
  }
  const save = (slide: SlideData) =>
    run(() => api.put(`/api/slides/${current.id}`, slide)).then(async (ok) => {
      if (ok) {
        await reload()
        setEditing(false)
      }
    })
  const regenerate = () =>
    run(() => api.post(`/api/slides/${current.id}/regenerate`, { instruction })).then(
      async (ok) => {
        if (ok) {
          await reload()
          setInstruction('')
        }
      },
    )
  const exportAs = (format: 'pptx' | 'pdf') =>
    run(() => api.post<Deck>(`${base}/deck/export`, { format })).then((d) => d && setDeck(d))

  return (
    <div className="deck">
      <nav className="panel deck-strip" aria-label="Slides">
        <ol>
          {deck.slides.map((s, i) => (
            <li key={s.id}>
              <button
                className={s.id === current.id ? 'current' : undefined}
                onClick={() => setIndex(i)}
              >
                <span className="kicker">{s.slide.kicker}</span>
                {s.slide.title}
              </button>
            </li>
          ))}
        </ol>
      </nav>
      <div className="stack">
        <section className="panel">
          <SlideView entry={current} position={[index + 1, deck.slides.length]} />
        </section>
        <section className="panel stack">
          <div className="row">
            <button disabled={busy || index === 0} onClick={() => move(-1)}>
              Move up
            </button>
            <button disabled={busy || index === deck.slides.length - 1} onClick={() => move(1)}>
              Move down
            </button>
            <button onClick={() => setEditing(!editing)}>
              {editing ? 'Cancel edit' : 'Edit text'}
            </button>
          </div>
          {editing ? (
            <Editor key={current.id} slide={current.slide} onSave={save} />
          ) : (
            <>
              <h2>Speaker notes</h2>
              <p>{current.slide.notes}</p>
            </>
          )}
          <label className="field">
            <span>Regenerate this slide with an instruction</span>
            <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} />
          </label>
          <button disabled={busy || !instruction.trim()} onClick={regenerate}>
            {busy ? 'Working…' : 'Regenerate'}
          </button>
          {error && <p className="error">{error}</p>}
        </section>
      </div>
      <aside className="panel stack" aria-label="Export">
        <h2>Export</h2>
        <button className="primary" disabled={busy} onClick={() => exportAs('pptx')}>
          PowerPoint
        </button>
        <button disabled={busy} onClick={() => exportAs('pdf')}>
          PDF
        </button>
        <h3>Versions</h3>
        <ul>
          {deck.exports.map((e) => (
            <li key={e.id}>
              <a href={`${API_BASE}/api/exports/${e.id}/download`}>
                deck_v{e.version}.{e.format}
              </a>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
