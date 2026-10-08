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
    fakeApi({ 'GET /api/projects/current': null })
    renderAt(path)
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
  })

  it('navigates between screens from the nav', async () => {
    fakeApi({ 'GET /api/projects/current': null })
    renderAt('/')
    await userEvent.click(screen.getByRole('link', { name: 'Squad loadout' }))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Squad loadout')
    expect(screen.getByRole('link', { name: 'Squad loadout' })).toHaveClass('active')
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
