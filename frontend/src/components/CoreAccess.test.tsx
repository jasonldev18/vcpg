import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { fakeApi } from '../testing'
import { CoreAccess } from './CoreAccess'

const KEY = 'sk-ant-api03-pasted-key-WXYZ'

describe('CoreAccess', () => {
  it('tests and saves a pasted key, then shows only the last four characters', async () => {
    const calls = fakeApi({
      'GET /api/core/anthropic': { saved: false, last4: null },
      'PUT /api/core/anthropic': { saved: true, last4: 'WXYZ' },
    })
    render(<CoreAccess onClose={vi.fn()} />)
    expect(await screen.findByText('No key saved.')).toBeInTheDocument()
    const input = screen.getByLabelText('Paste a new Anthropic API key')
    await userEvent.type(input, KEY)
    await userEvent.click(screen.getByRole('button', { name: 'Test and save' }))
    expect(calls[1].body).toEqual({ key: KEY })
    expect(await screen.findByText(/ending in WXYZ/)).toBeInTheDocument()
    expect(input).toHaveValue('')
    expect(document.body.textContent).not.toContain(KEY)
  })

  it('shows why a key was rejected', async () => {
    fakeApi({
      'GET /api/core/anthropic': { saved: false, last4: null },
      'PUT /api/core/anthropic': new Response(
        JSON.stringify({ detail: 'Anthropic rejected this key.' }),
        {
          status: 502,
        },
      ),
    })
    render(<CoreAccess onClose={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('Paste a new Anthropic API key'), KEY)
    await userEvent.click(screen.getByRole('button', { name: 'Test and save' }))
    expect(await screen.findByText('Anthropic rejected this key.')).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    fakeApi({ 'GET /api/core/anthropic': { saved: true, last4: 'WXYZ' } })
    const onClose = vi.fn()
    render(<CoreAccess onClose={onClose} />)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
