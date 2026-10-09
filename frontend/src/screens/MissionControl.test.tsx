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
    expect(screen.getByLabelText('Deck: 0 of 2 slides')).toHaveTextContent('Deck 0/2')
    expect(calls.filter((c) => c.path === '/api/steps/1/teach')).toHaveLength(1)
  })

  it('tours the committed code, highlights lines, then opens the interview', async () => {
    const reviewed = makeStep({
      state: 'reviewed',
      tour: {
        stops: [{ file: 'app.py', line_start: 2, line_end: 3, explanation: '**Loads** data.' }],
      },
    })
    const interviewing = makeStep({
      state: 'interviewing',
      gate: [{ id: 5, agent: 'interviewer', role: 'assistant', content: 'Why cosine?' }],
    })
    fakeApi({
      'GET /api/projects/current': makeProject(),
      'GET /api/steps/1': reviewed,
      'GET /api/steps/1/file?path=app.py': {
        path: 'app.py',
        lines: ['import x', 'a = 1', 'b = 2'],
      },
      'POST /api/steps/1/advance': interviewing,
    })
    renderIt()
    expect(await screen.findByText('a = 1')).toBeInTheDocument()
    expect(screen.getByText('a = 1').closest('div')).toHaveClass('hl')
    expect(screen.getByText('import x').closest('div')).not.toHaveClass('hl')
    await userEvent.click(screen.getByRole('button', { name: 'Ask about line 2' }))
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue(
      'About app.py line 2: ',
    )
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

describe('MissionControl builds', () => {
  it('shows build controls while building and the weaker-isolation warning', async () => {
    const building = makeStep({
      state: 'taught',
      build: { running: true, paused: false, error: null, isolation: 'venv' },
    })
    const calls = fakeApi({
      'GET /api/projects/current': makeProject(),
      'GET /api/steps/1': building,
      'POST /api/steps/1/advance': makeStep({
        state: 'taught',
        build: { running: true, paused: true, error: null, isolation: 'venv' },
      }),
    })
    renderIt()
    expect(await screen.findByText(/isolation is weaker/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(calls.at(-1)?.body).toEqual({ action: 'pause' })
    expect(await screen.findByRole('button', { name: 'Resume' })).toBeInTheDocument()
  })

  it('offers a retry after a failed build', async () => {
    fakeApi({
      'GET /api/projects/current': makeProject(),
      'GET /api/steps/1': makeStep({
        state: 'taught',
        build: { running: false, paused: false, error: 'max turns', isolation: 'docker' },
      }),
    })
    renderIt()
    expect(await screen.findByRole('button', { name: 'Retry build' })).toBeInTheDocument()
    expect(screen.getByText('max turns')).toBeInTheDocument()
  })
})

describe('MissionControl blocked steps', () => {
  it('asks the planner for a revision and shows it side by side', async () => {
    const blocked = makeStep({
      state: 'blocked',
      review_note: { commands: [], cut: [], fixed: [], status: 'fail', failure: 'tests fail' },
    })
    const revised = makeProject({
      replan: {
        old: [{ title: 'KNN recommender core', goal: 'g' }],
        new: [{ title: 'Simpler recommender', goal: 'g2', concepts: [], component: 'backend' }],
        changes: [],
      },
    })
    const calls = fakeApi({
      'GET /api/projects/current': makeProject(),
      'GET /api/steps/1': blocked,
      'POST /api/projects/1/replan': revised,
    })
    renderIt()
    expect(await screen.findByText('tests fail')).toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox'), 'drop numpy')
    await userEvent.click(screen.getByRole('button', { name: 'Edit plan' }))
    expect(calls.at(-1)?.body).toEqual({ request: 'drop numpy' })
    expect(await screen.findByText('Simpler recommender')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve change' })).toBeInTheDocument()
  })
})
