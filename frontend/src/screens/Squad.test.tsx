import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeApi, SQUAD } from '../testing'
import { Squad } from './Squad'

describe('Squad loadout', () => {
  it('never offers low effort and shows depth and speed only', async () => {
    fakeApi({ 'GET /api/squad': SQUAD })
    render(<Squad />)
    expect(await screen.findByRole('heading', { name: 'Squad loadout' })).toBeInTheDocument()
    for (const e of ['medium', 'high', 'xhigh', 'max']) {
      expect(screen.getByRole('button', { name: e })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'low' })).toBeNull()
    expect(
      screen.getByRole('img', { name: /^Relative depth \d+ of 10, speed \d+ of 10$/ }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/cost/i)).toBeNull()
  })

  it('marks a changed agent custom, saves every agent, and resets to recommended', async () => {
    const calls = fakeApi({ 'GET /api/squad': SQUAD, 'PUT /api/squad': SQUAD })
    render(<Squad />)
    const planner = await screen.findByRole('button', { name: /Planner.*(recommended|custom)/ })
    expect(planner).toHaveTextContent('recommended')
    await userEvent.click(screen.getByRole('button', { name: /Sonnet 5\.5/ }))
    await userEvent.click(screen.getByRole('button', { name: 'max' }))
    expect(planner).toHaveTextContent('custom')

    await userEvent.click(screen.getByRole('button', { name: 'Save loadout' }))
    const body = calls.find((c) => c.method === 'PUT')?.body as { agents: { agent: string }[] }
    expect(body.agents).toHaveLength(SQUAD.length)
    expect(body.agents[0]).toEqual({ agent: 'planner', model: 'claude-sonnet-5-5', effort: 'max' })
    expect(
      await screen.findByText('Loadout saved. It applies to the next call.'),
    ).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Reset to recommended' }))
    expect(planner).toHaveTextContent('recommended')
  })

  it('switches crews', async () => {
    fakeApi({ 'GET /api/squad': SQUAD })
    render(<Squad />)
    await userEvent.click(await screen.findByRole('button', { name: 'Audit crew' }))
    expect(screen.getByRole('heading', { name: 'Rook' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Helpers' }))
    expect(screen.getByRole('heading', { name: 'Lesson builder' })).toBeInTheDocument()
  })
})
