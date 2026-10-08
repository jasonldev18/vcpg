import { NavLink, Outlet } from 'react-router'
import { SCREENS } from './screens'

export function Shell() {
  return (
    <>
      <header className="shell-header">
        <span className="brand shell-logo">VCPG</span>
        <nav>
          {SCREENS.map((s) => (
            <NavLink key={s.path} to={s.path} end>
              {s.title}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
    </>
  )
}
