import { useEffect, useState } from 'react'

export type RGB = [number, number, number]

export const SOLAR = {
  acc: [255, 155, 61] as RGB,
  acc2: [255, 77, 94] as RGB,
  acc3: [255, 210, 122] as RGB,
  you: [92, 225, 230] as RGB,
  dim: [107, 74, 48] as RGB,
  white: [255, 255, 255] as RGB,
}

export const rgba = (c: RGB, a: number) =>
  `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(1, a)).toFixed(3)})`

/** Size the canvas for the device pixel ratio and return a cleared 2D context in CSS pixels. */
export function fit(c: HTMLCanvasElement, w: number, h: number): CanvasRenderingContext2D | null {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
    c.width = Math.round(w * dpr)
    c.height = Math.round(h * dpr)
  }
  const g = c.getContext('2d')
  if (!g) return null // jsdom in tests has no canvas
  g.setTransform(dpr, 0, 0, dpr, 0, 0)
  g.clearRect(0, 0, w, h)
  return g
}

const MOTION_QUERY =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : null

/** prefers-reduced-motion, live: scenes draw one still frame instead of animating. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(MOTION_QUERY?.matches ?? false)
  useEffect(() => {
    const change = () => setReduced(MOTION_QUERY?.matches ?? false)
    MOTION_QUERY?.addEventListener('change', change)
    return () => MOTION_QUERY?.removeEventListener('change', change)
  }, [])
  return reduced
}

/** Run `draw(t)` every animation frame, or once when motion is reduced. */
export function useFrame(draw: (t: number) => void, still: boolean) {
  useEffect(() => {
    if (still) {
      draw(0)
      return
    }
    let raf = requestAnimationFrame(function loop(t) {
      draw(t)
      raf = requestAnimationFrame(loop)
    })
    return () => cancelAnimationFrame(raf)
  }, [draw, still])
}
