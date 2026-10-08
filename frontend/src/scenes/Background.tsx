import { useCallback, useEffect, useRef } from 'react'
import { fit, rgba, SOLAR, useFrame, useReducedMotion } from './canvas'

interface Ripple {
  x: number
  y: number
  t: number
}

const LIFE = 1700 // ms a ripple lasts
const SPACING = 22

// Motes with a cursor ripple (DESIGN 3.1, drawBg "motes" in MissionControl.dc.html). Also feeds
// the --rx/--ry/--mx/--my variables that tilt panels and move their highlight (DESIGN 3.2).
export function Background() {
  const canvas = useRef<HTMLCanvasElement>(null)
  const ripples = useRef<Ripple[]>([])
  const last = useRef<{ x: number; y: number } | null>(null)
  const still = useReducedMotion()

  useEffect(() => {
    const root = document.documentElement
    const move = (e: MouseEvent) => {
      const x = e.clientX
      const y = e.clientY
      root.style.setProperty('--rx', ((x / window.innerWidth) * 2 - 1).toFixed(3))
      root.style.setProperty('--ry', ((y / window.innerHeight) * 2 - 1).toFixed(3))
      root.style.setProperty('--mx', `${x}px`)
      root.style.setProperty('--my', `${y}px`)
      const l = last.current
      if (!l || Math.abs(x - l.x) + Math.abs(y - l.y) > 46) {
        last.current = { x, y }
        ripples.current = [...ripples.current.slice(-8), { x, y, t: performance.now() }]
      }
    }
    window.addEventListener('mousemove', move)
    return () => window.removeEventListener('mousemove', move)
  }, [])

  const draw = useCallback(
    (t: number) => {
      const c = canvas.current
      if (!c) return
      const w = window.innerWidth
      const h = window.innerHeight
      const g = fit(c, w, h)
      if (!g) return
      const live = (ripples.current = still ? [] : ripples.current.filter((r) => t - r.t < LIFE))
      for (let y = 11, row = 0; y < h; y += SPACING, row++) {
        for (let x = row % 2 ? 22 : 11; x < w; x += SPACING) {
          let ox = 0
          let oy = 0
          let a = 0
          for (const r of live) {
            const age = (t - r.t) / LIFE
            const radius = age * 280
            const dx = x - r.x
            const dy = y - r.y
            const d = Math.hypot(dx, dy) || 1
            const k = Math.exp(-((d - radius) ** 2) / 1100) * (1 - age)
            ox += (dx / d) * k
            oy += (dy / d) * k
            a += k
          }
          g.fillStyle = rgba(a > 0.35 ? SOLAR.acc3 : SOLAR.acc, 0.1 + a * 0.34)
          g.beginPath()
          g.arc(x + ox * 3.5, y + oy * 3.5, 1 + a * 0.9, 0, Math.PI * 2)
          g.fill()
        }
      }
    },
    [still],
  )
  useFrame(draw, still)

  return (
    <>
      <canvas ref={canvas} className="background" aria-hidden="true" />
      <div className="glow" aria-hidden="true" />
    </>
  )
}
