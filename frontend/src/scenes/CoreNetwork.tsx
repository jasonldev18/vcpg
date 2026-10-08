import { motion } from 'motion/react'
import { useCallback, useRef } from 'react'
import { fit, rgba, SOLAR, useFrame, useReducedMotion, type RGB } from './canvas'
import { CREW, spriteShadow } from './sprites'

const W = 680
const H = 450
const CX = 340
const CY = 214
const TAU = Math.PI * 2

interface Props {
  active: Set<string> // backend agent names that are running now
  youTurn: boolean
  onCore: () => void
}

// The orchestrator stage (DESIGN 3.3, drawStage with the blob core in MissionControl.dc.html).
export function CoreNetwork({ active, youTurn, onCore }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const still = useReducedMotion()

  const draw = useCallback(
    (t: number) => {
      const c = canvas.current
      if (!c) return
      const g = fit(c, W, H)
      if (!g) return
      const hotColour: RGB = youTurn ? SOLAR.you : SOLAR.acc
      g.globalCompositeOperation = 'lighter'
      g.lineCap = 'round'
      CREW.forEach((a, i) => {
        const on = active.has(a.id)
        const col = on ? hotColour : SOLAR.dim
        const dx = a.x - CX
        const dy = a.y - CY
        const d = Math.hypot(dx, dy)
        const ux = dx / d
        const uy = dy / d
        const x0 = CX + ux * 96
        const y0 = CY + uy * 96
        const x1 = a.x - ux * 44
        const y1 = a.y - uy * 44
        const bend = (i % 2 ? 1 : -1) * 22
        const mx = (x0 + x1) / 2 - uy * bend
        const my = (y0 + y1) / 2 + ux * bend
        const at = (u: number): [number, number] => [
          (1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u * u * x1,
          (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u * u * y1,
        ]
        g.shadowColor = rgba(col, 1)
        g.shadowBlur = on ? 14 : 0
        g.beginPath()
        g.moveTo(x0, y0)
        g.quadraticCurveTo(mx, my, x1, y1)
        g.setLineDash([9, 7])
        g.lineDashOffset = on ? -t / 28 : 0
        g.lineWidth = on ? 2.2 : 1
        g.strokeStyle = rgba(col, on ? 0.95 : 0.55)
        g.stroke()
        g.setLineDash([])
        if (on) {
          for (let k = 0; k < 3; k++) {
            const u = (t / 1300 + k / 3) % 1
            const trail = k === 1 ? SOLAR.acc2 : k === 2 ? SOLAR.acc3 : col
            for (let j = 0; j < 10; j++) {
              const uu = u - j * 0.017
              if (uu < 0) continue
              const [px, py] = at(uu)
              const size = 5.5 - j * 0.45
              g.fillStyle = rgba(j === 0 ? SOLAR.white : trail, 1 - j / 10)
              g.fillRect(px - size / 2, py - size / 2, size, size)
            }
          }
          g.shadowBlur = 0
          for (let k = 0; k < 2; k++) {
            const pr = (t / 1100 + k / 2) % 1
            g.beginPath()
            g.arc(a.x, a.y + 6, 40 + pr * 18, 0, TAU)
            g.lineWidth = 1.5
            g.strokeStyle = rgba(col, (1 - pr) * 0.6)
            g.stroke()
          }
        } else {
          g.shadowBlur = 0
          const [px, py] = at((t / 5200 + i / 7) % 1)
          g.fillStyle = rgba(SOLAR.acc, 0.5)
          g.fillRect(px - 1.5, py - 1.5, 3, 3)
        }
      })
      g.shadowBlur = 0
      const pulse = 0.5 + 0.5 * Math.sin(t / 600)
      const glow = g.createRadialGradient(CX, CY, 2, CX, CY, 88)
      glow.addColorStop(0, rgba(SOLAR.white, 0.95))
      glow.addColorStop(0.16, rgba(hotColour, 0.9))
      glow.addColorStop(0.45, rgba(SOLAR.acc2, 0.28 + 0.14 * pulse))
      glow.addColorStop(1, rgba(SOLAR.acc2, 0))
      g.fillStyle = glow
      g.beginPath()
      g.arc(CX, CY, 88, 0, TAU)
      g.fill()
      const rings: RGB[] = [hotColour, SOLAR.acc2, SOLAR.acc3, hotColour]
      for (let l = 0; l < 4; l++) {
        g.beginPath()
        for (let a = 0; a < TAU; a += 0.1) {
          const r =
            38 + l * 11 + 6 * Math.sin(a * 3 + t / 700 + l) + 4 * Math.sin(a * 5 - t / 520 + l * 2)
          const x = CX + Math.cos(a) * r
          const y = CY + Math.sin(a) * r
          if (a === 0) g.moveTo(x, y)
          else g.lineTo(x, y)
        }
        g.closePath()
        g.lineWidth = 2
        g.strokeStyle = rgba(rings[l], 0.85 - l * 0.13)
        g.stroke()
      }
      for (let k = 0; k < 9; k++) {
        const a = k * 0.7 + t / (1400 + k * 90)
        const r = 70 + 14 * Math.sin(t / 900 + k)
        g.fillStyle = rgba(rings[k % 3], 0.8)
        g.fillRect(CX + Math.cos(a) * r - 1.5, CY + Math.sin(a) * r - 1.5, 3, 3)
      }
      g.globalCompositeOperation = 'source-over'
    },
    [active, youTurn],
  )
  useFrame(draw, still)

  const working = CREW.filter((a) => active.has(a.id)).map((a) => `${a.name} is ${a.doing}`)
  const label = `Agent network. ${working.length ? working.join(', ') : youTurn ? 'It is your turn.' : 'Every agent is on standby.'}`
  return (
    <div className={`stage${youTurn ? ' you' : ''}`}>
      <canvas ref={canvas} className="stage-canvas" role="img" aria-label={label} />
      <div className="stage-core-label">
        <span className="disp">Orchestrator</span>
        <span className="mono mute">click the core for access</span>
      </div>
      <motion.button
        layoutId="core"
        className="core-button-stage"
        onClick={onCore}
        aria-label="Open core access to enter your API key and GitHub token"
      />
      {CREW.map((a, i) => {
        const on = active.has(a.id)
        return (
          <div
            key={a.id}
            className={`node${on ? ' on' : ''}`}
            style={{ left: a.x - 60, top: a.y - 30 }}
          >
            <div className="pad">
              <div className="spr" style={{ animationDelay: `${(i * 0.37).toFixed(2)}s` }}>
                <div className="px" style={{ boxShadow: spriteShadow(a, '#FF9B3D') }} />
                <div
                  className="px lid"
                  style={{
                    boxShadow: spriteShadow(a, '#FF9B3D', true),
                    animationDelay: `${(i * 0.37).toFixed(2)}s`,
                  }}
                />
              </div>
              {on && (
                <>
                  <div className="spark s1" />
                  <div className="spark s2" />
                  <div className="spark s3" />
                </>
              )}
            </div>
            <span className="disp node-name">{a.name}</span>
            <span className="mono node-doing">{on ? a.doing : 'standby'}</span>
          </div>
        )
      })}
    </div>
  )
}
