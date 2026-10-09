import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { AuditState } from '../api/types'
import { fakeApi } from '../testing'
import { AuditBay, AuditPill } from './AuditBay'

const IDLE: AuditState = {
  current: null,
  runs: [{ id: 1, kind: 'deep', status: 'done', started_at: '2026-10-01', finished_at: null }],
  issues: [
    {
      id: 1,
      run_id: 1,
      agent: 'interviewer',
      severity: 'high',
      title: 'Hint gave the answer',
      evidence: '[]',
      status: 'open',
    },
  ],
  prs: [
    {
      id: 1,
      run_id: 1,
      branch: 'audit/1/slide-wording',
      pr_url: 'https://github.com/x/pull/1',
      auto_merge: 1,
      state: 'merged',
    },
    {
      id: 2,
      run_id: 1,
      branch: 'audit/1/grader-wording',
      pr_url: 'https://github.com/x/pull/2',
      auto_merge: 0,
      state: 'open',
    },
  ],
  next_deep_scan: '2026-10-15T00:00:00',
  github: true,
}

describe('Audit bay', () => {
  it('lists issues and pull requests and starts a deep scan', async () => {
    const running = {
      ...IDLE,
      current: { run_id: 2, kind: 'deep' as const, stage: 'COLLECTING REPORTS' },
    }
    const calls = fakeApi({ 'GET /api/audit': IDLE, 'POST /api/audit/run': running })
    render(
      <MemoryRouter>
        <AuditBay />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Hint gave the answer')).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: /offline, agents resting\. 1 open issues, 2 pull requests/ }),
    ).toBeInTheDocument()
    expect(screen.getByText('MERGED')).toBeInTheDocument()
    expect(screen.getByText('READY TO REVIEW')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'audit/1/grader-wording' })).toHaveAttribute(
      'href',
      'https://github.com/x/pull/2',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Run a deep scan now' }))
    expect(calls.at(-1)?.path).toBe('/api/audit/run')
    expect(await screen.findByText('COLLECTING REPORTS')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /deep scan: COLLECTING REPORTS/ })).toBeInTheDocument()
  })

  it('warns when no GitHub token is saved', async () => {
    fakeApi({ 'GET /api/audit': { ...IDLE, github: false } })
    render(
      <MemoryRouter>
        <AuditBay />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/no pull requests are opened/)).toBeInTheDocument()
  })

  it('the pill shows the scan state and links to the bay', async () => {
    fakeApi({ 'GET /api/audit': IDLE })
    render(
      <MemoryRouter>
        <AuditPill />
      </MemoryRouter>,
    )
    const pill = await screen.findByRole('link', { name: 'Audit: Offline' })
    expect(pill).toHaveAttribute('href', '/audit')
    expect(await screen.findByText(/1 to review/)).toBeInTheDocument()
  })
})

describe('Audit pill', () => {
  it('counts the issues and fixes of the running deep scan', async () => {
    fakeApi({
      'GET /api/audit': {
        ...IDLE,
        current: { run_id: 1, kind: 'deep', stage: 'TRACING CAUSES' },
      },
    })
    render(
      <MemoryRouter>
        <AuditPill />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('link', { name: 'Audit: Deep scan' })).toBeInTheDocument()
    expect(screen.getByText('TRACING CAUSES')).toBeInTheDocument()
    expect(screen.getByText('1 issue / 2 fixes so far')).toBeInTheDocument()
  })
})
