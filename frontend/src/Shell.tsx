import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { CoreAccess } from './components/CoreAccess'
import { SCREENS } from './screens'

export function Shell() {
  const [coreOpen, setCoreOpen] = useState(false)
  return (
    <>
      <header className="shell-header">
        <span className="brand shell-logo">VCPG</span>
        <nav>
          {SCREENS.map((s) =>
            s.phase ? (
              <span key={s.path} className="nav-soon" aria-disabled="true">
                {s.title} <small>Phase {s.phase}</small>
              </span>
            ) : (
              <NavLink key={s.path} to={s.path} end>
                {s.title}
              </NavLink>
            ),
          )}
        </nav>
        <button className="core-button" onClick={() => setCoreOpen(true)}>
          Core access
        </button>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
      {coreOpen && <CoreAccess onClose={() => setCoreOpen(false)} />}
    </>
  )
}
