import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { PlanView } from '../api/types'
import { fakeApi, makeProject } from '../testing'
import { PlanReview } from './PlanReview'

const step = (title: string) => ({
  title,
  goal: `${title} goal`,
  concepts: ['c'],
  component: 'backend',
})
const PLAN: PlanView = {
  questions: [],
  project_name: 'Movie Recommender',
  one_liner: 'Recommends films.',
  stack: ['Python'],
  changes_from_spine: [],
  steps: [step('Loader'), step('Recommender'), step('Evaluation')],
}

describe('PlanReview', () => {
  it('sends answers to the planner questions', async () => {
    const plan = { ...PLAN, questions: ['Where is the data?'], steps: [] }
    const calls = fakeApi({ 'POST /api/projects/1/plan/answers': makeProject() })
    const onChange = vi.fn()
    render(<PlanReview project={makeProject({ plan })} plan={plan} onChange={onChange} />)
    await userEvent.type(screen.getByRole('textbox'), 'MovieLens')
    await userEvent.click(screen.getByRole('button', { name: 'Send answers' }))
    expect(calls[0].body).toEqual({ answers: ['MovieLens'] })
    expect(onChange).toHaveBeenCalled()
  })

  it('saves reorder, rename and drop before approving', async () => {
    const calls = fakeApi({
      'PUT /api/projects/1/plan': makeProject({ plan: PLAN }),
      'POST /api/projects/1/plan/approve': makeProject(),
    })
    render(<PlanReview project={makeProject({ plan: PLAN })} plan={PLAN} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Move step 2 up' }))
    await userEvent.click(screen.getByRole('button', { name: 'Drop step 3' }))
    const title = screen.getByRole('textbox', { name: 'Title of step 2' })
    await userEvent.clear(title)
    await userEvent.type(title, 'Data loader')
    await userEvent.click(screen.getByRole('button', { name: 'Approve plan' }))
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      'PUT /api/projects/1/plan',
      'POST /api/projects/1/plan/approve',
    ])
    expect(calls[0].body).toEqual({
      steps: [
        { source: 1, title: 'Recommender' },
        { source: 0, title: 'Data loader' },
      ],
    })
  })

  it('approves an unedited plan without saving first', async () => {
    const calls = fakeApi({ 'POST /api/projects/1/plan/approve': makeProject() })
    render(<PlanReview project={makeProject({ plan: PLAN })} plan={PLAN} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Approve plan' }))
    expect(calls.map((c) => c.method)).toEqual(['POST'])
  })

  it('shows the server error when approval fails', async () => {
    fakeApi({
      'POST /api/projects/1/plan/approve': new Response(
        JSON.stringify({ detail: 'Answer the planner first.' }),
        { status: 409 },
      ),
    })
    render(<PlanReview project={makeProject({ plan: PLAN })} plan={PLAN} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Approve plan' }))
    expect(await screen.findByText('Answer the planner first.')).toBeInTheDocument()
  })
})
