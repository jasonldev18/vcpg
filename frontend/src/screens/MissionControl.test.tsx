import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { fakeApi, makeProject, makeStep } from '../testing'
import { MissionControl } from './MissionControl'

const renderIt = () =>
  render(
    <MemoryRouter>
      <MissionControl />
    </MemoryRouter>,
  )

describe('MissionControl', () => {
  it('teaches the current step and locks the rest', async () => {
    const lesson = makeStep({ lesson: '## What we are building\nA recommender.' })
    const project = makeProject({
      steps: [
        makeStep(),
        makeStep({ id: 2, position: 1, title: 'Offline evaluation', current: false }),
      ],
    })
    const calls = fakeApi({
      'GET /api/projects/current': project,
      'GET /api/steps/1': makeStep(),
      'POST /api/steps/1/teach': lesson,
    })
    renderIt()
    expect(await screen.findByRole('heading', { name: 'What we are building' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Steps' })).toHaveTextContent(
      'Offline evaluationlocked',
    )
    expect(calls.filter((c) => c.path === '/api/steps/1/teach')).toHaveLength(1)
  })

  it('moves from the tour placeholder into the interview', async () => {
    const reviewed = makeStep({ state: 'reviewed', build_note: 'Building arrives in phase 2.' })
    const interviewing = makeStep({
      state: 'interviewing',
      gate: [{ id: 5, agent: 'interviewer', role: 'assistant', content: 'Why cosine?' }],
    })
    fakeApi({
      'GET /api/projects/current': makeProject(),
      'GET /api/steps/1': reviewed,
      'POST /api/steps/1/advance': interviewing,
    })
    renderIt()
    await userEvent.click(
      await screen.findByRole('button', { name: "I'm ready for the interview" }),
    )
    expect(await screen.findByText('Why cosine?')).toBeInTheDocument()
    expect(screen.getByText('0 of 4 points covered')).toBeInTheDocument()
  })

  it('links to the start screen when there is no project', async () => {
    fakeApi({ 'GET /api/projects/current': null })
    renderIt()
    expect(await screen.findByRole('link', { name: 'Start a project' })).toBeInTheDocument()
  })
})
