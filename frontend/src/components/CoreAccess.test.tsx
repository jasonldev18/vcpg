import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { fakeApi } from '../testing'
import { CoreAccess } from './CoreAccess'

const KEY = 'sk-ant-api03-pasted-key-WXYZ'
const NONE = { saved: false, last4: null }

describe('CoreAccess', () => {
  it('tests and saves a pasted key, then shows only the last four characters', async () => {
    const calls = fakeApi({
      'GET /api/core/anthropic': NONE,
      'GET /api/core/github': { ...NONE, found: [], problems: [] },
      'PUT /api/core/anthropic': { saved: true, last4: 'WXYZ' },
    })
    render(<CoreAccess onClose={vi.fn()} />)
    expect(await screen.findAllByText('Not saved.')).toHaveLength(2)
    const input = screen.getByLabelText('Paste a new Anthropic API key')
    await userEvent.type(input, KEY)
    const panel = input.closest('section') as HTMLElement
    await userEvent.click(within(panel).getByRole('button', { name: 'Test and save' }))
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ key: KEY })
    expect(await screen.findByText(/ending in WXYZ/)).toBeInTheDocument()
    expect(input).toHaveValue('')
    expect(document.body.textContent).not.toContain(KEY)
  })

  it('shows why a key was rejected', async () => {
    fakeApi({
      'GET /api/core/anthropic': NONE,
      'GET /api/core/github': { ...NONE, found: [], problems: [] },
      'PUT /api/core/anthropic': new Response(
        JSON.stringify({ detail: 'Anthropic rejected this key.' }),
        { status: 502 },
      ),
    })
    render(<CoreAccess onClose={vi.fn()} />)
    const input = screen.getByLabelText('Paste a new Anthropic API key')
    await userEvent.type(input, KEY)
    await userEvent.click(
      within(input.closest('section') as HTMLElement).getByRole('button', {
        name: 'Test and save',
      }),
    )
    expect(await screen.findByText('Anthropic rejected this key.')).toBeInTheDocument()
  })

  it('refuses a GitHub token that is broader than it needs and lists what it found', async () => {
    fakeApi({
      'GET /api/core/anthropic': NONE,
      'GET /api/core/github': { ...NONE, found: [], problems: [] },
      'PUT /api/core/github': {
        saved: false,
        last4: null,
        found: ['Metadata: read', 'Administration (/repos/x/keys)'],
        problems: ['Has Administration'],
      },
    })
    render(<CoreAccess onClose={vi.fn()} />)
    const input = screen.getByLabelText('Paste a fine-grained GitHub token')
    await userEvent.type(input, 'github_pat_11AAAA0123456789abcdef')
    await userEvent.click(
      within(input.closest('section') as HTMLElement).getByRole('button', {
        name: 'Test and save',
      }),
    )
    expect(await screen.findByText('Refused: Has Administration')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Permissions found' })).toHaveTextContent(
      'Administration',
    )
    expect(screen.getByText('Not saved: see the problems below.')).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    fakeApi({
      'GET /api/core/anthropic': { saved: true, last4: 'WXYZ' },
      'GET /api/core/github': { ...NONE, found: [], problems: [] },
    })
    const onClose = vi.fn()
    render(<CoreAccess onClose={onClose} />)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
