import { MotionConfig } from 'motion/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { routes } from './routes'
import './theme/tokens.css'
import './shell.css'

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    {/* under reduced motion, Motion drops movement and keeps fades (DESIGN 3) */}
    <MotionConfig reducedMotion="user">
      <RouterProvider router={createBrowserRouter(routes)} />
    </MotionConfig>
  </StrictMode>,
)
