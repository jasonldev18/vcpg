import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { ArchivedProject, MockInterview, Readme } from '../api/types'
import { fakeApi, makeProject } from '../testing'
import { Archive } from './Archive'
import { ReadmeCoach } from './ReadmeCoach'

const atReadme = makeProject({
  status: 'finishing',
  current_step_id: null,
  finish: {
    stage: 'readme',
    final_review: null,
    final_review_status: { running: false, error: null },
    retest: null,
  },
})

const readme = (over: Partial<Readme>): Readme => ({
  template: '# T',
  content: '# Movie Recommender\nUses Euclidean distance.',
  review: null,
  ready: false,
  ...over,
})

describe('ReadmeCoach', () => {
  it('writes the template on first visit, then reviews and shows tagged notes', async () => {
    const reviewed = readme({
      review: {
        notes: [
          {
            line: 2,
            kind: 'does_not_match',
            note: 'The code uses another measure.',
            project_shows: 'recommend.py uses cosine',
          },
        ],
      },
    })
    const calls = fakeApi({
      'GET /api/projects/current': atReadme,
      'GET /api/projects/1/readme': null,
      'POST /api/projects/1/readme/template': readme({}),
      'PUT /api/projects/1/readme': readme({}),
      'POST /api/projects/1/readme/review': reviewed,
    })
    render(
      <MemoryRouter>
        <ReadmeCoach />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Movie Recommender' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'README' })).toHaveValue(
      '# Movie Recommender\nUses Euclidean distance.',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Ask the coach to review' }))
    expect(await screen.findByText('does not match')).toBeInTheDocument()
    expect(screen.getByText('The project shows: recommend.py uses cosine')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Finish the project' })).toBeNull()
    expect(calls.map((c) => `${c.method} ${c.path}`)).toContain('PUT /api/projects/1/readme')
  })

  it('offers to finish once the coach passes it', async () => {
    fakeApi({
      'GET /api/projects/current': atReadme,
      'GET /api/projects/1/readme': readme({ ready: true, review: { notes: [] } }),
    })
    render(
      <MemoryRouter>
        <ReadmeCoach />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('button', { name: 'Finish the project' })).toBeInTheDocument()
    expect(screen.getByText('Ready: no mismatches or gaps.')).toBeInTheDocument()
  })
})

const archived: ArchivedProject = {
  id: 1,
  name: 'Movie Recommender',
  stack: ['Python'],
  finished_at: '2026-10-08 12:00:00',
  dossier: '## Mission\nRecommends films.',
  readme: '# README',
  exports: [{ id: 3, version: 1, format: 'pdf', created_at: 'now' }],
  mocks: [],
}

const interview = (over: Partial<MockInterview>): MockInterview => ({
  id: 9,
  project_id: 1,
  length_min: 10,
  focus: 'system_design',
  seconds_left: 600,
  ended: false,
  transcript: [{ role: 'interviewer', text: 'How would it scale?' }],
  scorecard: null,
  ...over,
})

describe('Archive', () => {
  it('shows the dossier and runs a timed mock interview with a scorecard', async () => {
    const scored = interview({
      ended: true,
      seconds_left: 0,
      transcript: [
        { role: 'interviewer', text: 'How would it scale?' },
        { role: 'learner', text: 'Cache the neighbours per user.' },
      ],
      scorecard: {
        dimensions: [
          { name: 'system_design', score: 4, evidence: 'Cache the neighbours', reason: 'r' },
          { name: 'failure_modes', score: 2, evidence: null, reason: 'r' },
          { name: 'motivation_and_impact', score: 3, evidence: null, reason: 'r' },
          { name: 'communication', score: 4, evidence: null, reason: 'r' },
        ],
        practise: ['Explain cold start'],
      },
    })
    const calls = fakeApi({
      'GET /api/archive': [archived],
      'POST /api/archive/1/mock': interview({}),
      'POST /api/mock/9/end': scored,
    })
    render(<Archive />)
    expect(await screen.findByRole('heading', { name: 'Mission' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'deck_v1.pdf' })).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Length'), '10')
    await userEvent.selectOptions(screen.getByLabelText('Focus'), 'system_design')
    await userEvent.click(screen.getByRole('button', { name: 'Start the interview' }))
    expect(calls.at(-1)?.body).toEqual({ length_min: 10, focus: 'system_design' })
    expect(await screen.findByText('10:00 left')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'End and score' }))
    expect(await screen.findByText('System design: 4 / 5')).toBeInTheDocument()
    expect(screen.getByText('“Cache the neighbours”')).toBeInTheDocument()
    expect(screen.getByText('Explain cold start')).toBeInTheDocument()
  })
})
