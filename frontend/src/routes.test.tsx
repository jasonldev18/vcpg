import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'
import { routes } from './routes'
import { SCREENS } from './screens'

const renderAt = (path: string) =>
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)

describe('app shell', () => {
  it.each(SCREENS)('renders $title at $path', ({ path, title }) => {
    renderAt(path)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(title)
  })

  it('navigates between screens from the nav', async () => {
    renderAt('/')
    await userEvent.click(screen.getByRole('link', { name: 'Squad loadout' }))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Squad loadout')
    expect(screen.getByRole('link', { name: 'Squad loadout' })).toHaveClass('active')
  })
})
