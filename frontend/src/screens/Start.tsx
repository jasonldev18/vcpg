import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../api/client'
import type { Project } from '../api/types'
import { useAction } from '../components/useAction'

// Phase 1 ships the "I have a plan" path; ideas and lessons arrive in phase 6.
export function Start() {
  const [brief, setBrief] = useState('')
  const { busy, error, run } = useAction()
  const navigate = useNavigate()

  const start = async () => {
    if (await run(() => api.post<Project>('/api/projects', { brief }))) navigate('/')
  }

  return (
    <section className="panel stack start">
      <h1>Start a project</h1>
      <h2>I have a plan</h2>
      <label className="field">
        <span>What do you want to build? Goal, rough features, any stack preferences.</span>
        <textarea
          rows={8}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="A movie recommender that suggests five films from my MovieLens ratings…"
        />
      </label>
      <button className="primary" disabled={busy || !brief.trim()} onClick={start}>
        {busy ? 'The planner is drafting…' : 'Plan it'}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
