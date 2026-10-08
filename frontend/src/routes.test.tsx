import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'
import { routes } from './routes'
import { SCREENS } from './screens'
import { fakeApi } from './testing'

const renderAt = (path: string) =>
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)

describe('app shell', () => {
  it.each(SCREENS)('renders $title at $path', async ({ path, title }) => {
    fakeApi({
      'GET /api/projects/current': null,
      'GET /api/archive': [],
      'GET /api/lessons': [],
      'GET /api/sources': [],
    })
    renderAt(path)
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
  })

  it('navigates between built screens from the nav', async () => {
    fakeApi({ 'GET /api/projects/current': null })
    renderAt('/')
    await userEvent.click(screen.getByRole('link', { name: 'Start a project' }))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Start a project')
  })

  it('greys out screens that are not built yet, with their phase', () => {
    fakeApi({ 'GET /api/projects/current': null })
    renderAt('/')
    for (const s of SCREENS.filter((s) => s.phase)) {
      expect(screen.queryByRole('link', { name: s.title })).toBeNull()
      expect(screen.getByText(s.title)).toHaveAttribute('aria-disabled', 'true')
      expect(screen.getByText(s.title)).toHaveTextContent(`Phase ${s.phase}`)
    }
  })

  it('starts a project from a brief and returns to mission control', async () => {
    const calls = fakeApi({ 'POST /api/projects': {}, 'GET /api/projects/current': null })
    renderAt('/start')
    await userEvent.type(screen.getByRole('textbox'), 'A movie recommender')
    await userEvent.click(screen.getByRole('button', { name: 'Plan it' }))
    expect(await screen.findByRole('heading', { name: 'Mission control' })).toBeInTheDocument()
    expect(calls[0]).toEqual({
      method: 'POST',
      path: '/api/projects',
      body: { brief: 'A movie recommender' },
    })
  })
})
