import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Project, Readme } from '../api/types'
import { Markdown } from '../components/Markdown'
import { useAction } from '../components/useAction'

const KIND_LABEL = { does_not_match: 'does not match', gap: 'gap', unclear: 'unclear' }

export function ReadmeCoach() {
  const [project, setProject] = useState<Project | null | undefined>(undefined)
  const [readme, setReadme] = useState<Readme | null>(null)
  const [text, setText] = useState('')
  const { busy, error, run } = useAction()
  const requested = useRef(false)

  useEffect(() => {
    void api.get<Project | null>('/api/projects/current').then(async (p) => {
      setProject(p)
      if (!p) return
      const r = await api.get<Readme | null>(`/api/projects/${p.id}/readme`)
      setReadme(r)
      setText(r?.content ?? '')
    })
  }, [])

  const atStage = project?.finish?.stage === 'readme'
  useEffect(() => {
    if (!project || !atStage || readme || requested.current) return
    requested.current = true
    void run(() => api.post<Readme>(`/api/projects/${project.id}/readme/template`)).then((r) => {
      if (r) {
        setReadme(r)
        setText(r.content)
      }
    })
  }, [project, atStage, readme, run])

  if (project === undefined) return <p className="mute">Loading…</p>
  if (!project || (!atStage && !readme))
    return (
      <section className="panel stack">
        <h1>README coach</h1>
        <p className="mute">The README comes after the deck, once every step has passed.</p>
      </section>
    )

  const base = `/api/projects/${project.id}/readme`
  const review = async () => {
    const saved = await run(() => api.put<Readme>(base, { content: text }))
    if (!saved) return
    const reviewed = await run(() => api.post<Readme>(`${base}/review`))
    if (reviewed) setReadme(reviewed)
  }
  const finish = () =>
    run(() => api.post<Readme>(`${base}/finish`)).then(async (r) => {
      if (r) setProject(await api.get<Project>(`/api/projects/${project.id}`))
    })
  const notes = readme?.review?.notes ?? []
  const done = project.status === 'done'
  const dirty = readme !== null && text !== readme.content

  return (
    <div className="readme">
      <section className="panel stack">
        <h1>README coach</h1>
        <p className="mute">
          You write the README. The coach checks every claim against the project.
        </p>
        <textarea
          className="readme-editor"
          aria-label="README"
          value={text}
          onChange={(e) => setText(e.target.value)}
          readOnly={done}
        />
        <div className="row">
          <button className="primary" disabled={busy || done || !text.trim()} onClick={review}>
            {busy ? 'Working…' : 'Ask the coach to review'}
          </button>
          {readme?.ready && !dirty && !done && (
            <button className="primary" disabled={busy} onClick={finish}>
              Finish the project
            </button>
          )}
        </div>
        <p aria-live="polite">
          {done ? (
            <>
              Committed and archived. <Link to="/archive">Open the archive</Link>
            </>
          ) : readme?.ready && !dirty ? (
            <span className="ok">Ready: no mismatches or gaps.</span>
          ) : readme?.review ? (
            'Not ready yet: fix the notes marked does not match or gap, then ask again.'
          ) : (
            'Not reviewed yet.'
          )}
        </p>
        {error && <p className="error">{error}</p>}
      </section>
      <section className="panel stack" aria-label="Preview">
        <h2>Preview</h2>
        <Markdown text={text} />
      </section>
      <aside className="panel stack" aria-label="Coach notes">
        <h2>Coach notes</h2>
        {notes.length === 0 && <p className="mute">No notes.</p>}
        <ol className="coach-notes">
          {notes.map((n, i) => (
            <li key={i} className={n.kind}>
              <span className="tag">{KIND_LABEL[n.kind]}</span> line {n.line}
              <p>{n.note}</p>
              <p className="mute">The project shows: {n.project_shows}</p>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  )
}
