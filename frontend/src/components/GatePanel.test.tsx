import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { fakeApi, makeStep } from '../testing'
import { GatePanel } from './GatePanel'

const asked = makeStep({
  state: 'interviewing',
  gate: [{ id: 1, agent: 'interviewer', role: 'assistant', content: 'Why mean-centre?' }],
})

describe('GatePanel', () => {
  it('shows progress as a count and the conversation', () => {
    render(
      <GatePanel
        step={{ ...asked, progress: { covered: 1, total: 4 } }}
        live={{}}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('1 of 4 points covered')).toBeInTheDocument()
    expect(screen.getByText('Why mean-centre?')).toBeInTheDocument()
  })

  it('offers hints only after an answer', () => {
    render(<GatePanel step={asked} live={{}} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Hint' })).toBeDisabled()
  })

  it('sends the answer and clears the box', async () => {
    const next = makeStep({ ...asked, can_hint: true })
    const calls = fakeApi({ 'POST /api/steps/1/gate/answer': next })
    const onChange = vi.fn()
    render(<GatePanel step={asked} live={{}} onChange={onChange} />)
    const box = screen.getByRole('textbox', { name: 'Your answer' })
    await userEvent.type(box, 'It removes rating bias.')
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(calls[0].body).toEqual({ answer: 'It removes rating bias.' })
    expect(onChange).toHaveBeenCalledWith(next)
    expect(box).toHaveValue('')
  })

  it('asks for a re-teach on request', async () => {
    const calls = fakeApi({ 'POST /api/steps/1/gate/reteach': asked })
    render(<GatePanel step={asked} live={{}} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Teach me this again' }))
    expect(calls[0].path).toBe('/api/steps/1/gate/reteach')
  })
})
