import type { RouteObject } from 'react-router'
import { Archive } from './screens/Archive'
import { DeckViewer } from './screens/DeckViewer'
import { LessonScreen } from './screens/LessonScreen'
import { MissionControl } from './screens/MissionControl'
import { ReadmeCoach } from './screens/ReadmeCoach'
import { Start } from './screens/Start'
import { SCREENS } from './screens'
import { Shell } from './Shell'

const BUILT: Record<string, React.ReactNode> = {
  '/': <MissionControl />,
  '/start': <Start />,
  '/deck': <DeckViewer />,
  '/readme': <ReadmeCoach />,
  '/archive': <Archive />,
  '/lesson': <LessonScreen />,
}

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: [
      { path: '/lesson/:id', element: <LessonScreen /> },
      ...SCREENS.map((s) => ({
        path: s.path,
        element: BUILT[s.path] ?? (
          <section className="panel">
            <h1>{s.title}</h1>
            <p className="mute">This screen arrives in phase {s.phase}.</p>
          </section>
        ),
      })),
    ],
  },
]
