import type { RouteObject } from 'react-router'
import { MissionControl } from './screens/MissionControl'
import { Start } from './screens/Start'
import { SCREENS } from './screens'
import { Shell } from './Shell'

const BUILT: Record<string, React.ReactNode> = {
  '/': <MissionControl />,
  '/start': <Start />,
}

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: SCREENS.map((s) => ({
      path: s.path,
      element: BUILT[s.path] ?? (
        <section className="panel">
          <h1>{s.title}</h1>
          <p className="mute">This screen arrives in phase {s.phase}.</p>
        </section>
      ),
    })),
  },
]
