import type { RouteObject } from 'react-router'
import { SCREENS } from './screens'
import { Shell } from './Shell'

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: SCREENS.map((s) => ({
      path: s.path,
      element: (
        <section className="panel">
          <h1>{s.title}</h1>
        </section>
      ),
    })),
  },
]
