// The audit crew: black suits, white shirts, coloured ties, sunglasses (DESIGN 4.2).
// Drawing code from Squad.dc.html's `fig`, in "units" scaled by `s`, feet at (x, y).

export type AuditId = 'rook' | 'bolt' | 'echo' | 'pixel'

interface Look {
  tie: string
  tieD: string
  skin: string
  skinD: string
  hair: string
  hl: string
  coat?: boolean
  mic?: boolean
  pocket?: string
}

export const LOOKS: Record<AuditId, Look> = {
  rook: {
    tie: '#FF4D5E',
    tieD: '#B8303C',
    skin: '#E0B48F',
    skinD: '#C4936C',
    hair: '#C9CED6',
    hl: '#EEF0F4',
    coat: true,
  },
  bolt: {
    tie: '#5AA9FF',
    tieD: '#2F6FD0',
    skin: '#8D5A3B',
    skinD: '#6E4329',
    hair: '#2A1E16',
    hl: '#4A3A2E',
  },
  echo: {
    tie: '#41D6C3',
    tieD: '#1E9C8C',
    skin: '#F1C7A3',
    skinD: '#D8A884',
    hair: '#1A1420',
    hl: '#3A2E48',
    mic: true,
  },
  pixel: {
    tie: '#FFD45E',
    tieD: '#D9A62A',
    skin: '#C68B5E',
    skinD: '#A56E45',
    hair: '#F2C25A',
    hl: '#FFE7A0',
    pocket: '#FFD45E',
  },
}

export const CODES: Record<AuditId, string> = {
  rook: 'AGENT 001',
  bolt: 'AGENT 004',
  echo: 'AGENT 007',
  pixel: 'AGENT 009',
}

const SUIT = '#1C1E27'
const SUITD = '#111218'
const SUITL = '#2E3140'
const PANTS = '#15161D'
const SHOE = '#07070B'
const SHIRT = '#ECECF2'
const GLASSES = '#06060B'

/** One suited agent, standing. `t` (seconds) drives breathing and the glint on the glasses. */
export function drawSuit(g: CanvasRenderingContext2D, id: AuditId, x: number, y: number, s: number, t: number) {
  const A = LOOKS[id]
  const breath = (Math.floor(t * 1.2) % 2) * 0.4
  const R = (ux: number, uy: number, uw: number, uh: number, c: string) => {
    g.fillStyle = c
    const px = Math.round(x + ux * s)
    const py = Math.round(y + uy * s)
    g.fillRect(px, py, Math.max(1, Math.round(x + (ux + uw) * s) - px), Math.max(1, Math.round(y + (uy + uh) * s) - py))
  }
  const H = (ux: number, uy: number, uw: number, uh: number, c: string) => R(ux, uy + breath, uw, uh, c)
  R(-6.5, -0.6, 13, 1.2, 'rgba(0,0,0,0.4)')
  R(-4, -10, 3, 8.6, PANTS); R(1, -10, 3, 8.6, PANTS); R(-2.6, -10, 0.5, 8, '#20212B'); R(2.4, -10, 0.5, 8, '#20212B')
  R(-4.6, -1.5, 3.8, 1.5, SHOE); R(0.8, -1.5, 3.8, 1.5, SHOE); R(-4, -1.5, 1, 0.5, '#3A3F4C'); R(1.4, -1.5, 1, 0.5, '#3A3F4C')
  if (A.coat) { R(-6.3, -12, 12.6, 4, SUIT); R(-0.3, -12, 0.6, 4, SUITD) }
  R(-5.6, -20, 11.2, 10.6, SUIT); R(3.6, -20, 2, 10.6, SUITD); R(-5.6, -20, 1, 10.6, SUITL)
  R(-1.6, -20, 3.2, 4.6, SHIRT); R(-1, -15.4, 2, 1.4, SHIRT); R(-2.7, -20, 1.1, 5.6, SUITL); R(1.6, -20, 1.1, 5.6, SUITL)
  R(-0.5, -19.3, 1, 7.4, A.tie); R(-0.7, -19.8, 1.4, 1, A.tieD); R(-0.3, -11.8, 0.6, 0.6, '#3A3D4A'); R(-0.3, -13.6, 0.6, 0.6, '#3A3D4A')
  if (A.pocket) R(2.3, -18.2, 1.5, 0.9, A.pocket)
  R(-7.6, -19.6, 2, 9.6, SUIT); R(-7.6, -19.6, 0.6, 9.6, SUITL); R(-7.6, -10.2, 2, 1.6, A.skin)
  R(5.6, -19.6, 2, 9.6, SUIT); R(5.6, -19.6, 0.6, 9.6, SUITL); R(5.6, -10.2, 2, 1.6, A.skin)
  H(-1.6, -21.8, 3.2, 1.8, A.skinD)
  H(-4, -29, 8, 8, A.skin); H(-3.6, -21.6, 7.2, 0.8, A.skin); H(2.6, -28.6, 1.4, 7.2, A.skinD); H(-4.7, -26.2, 0.8, 2.2, A.skinD); H(3.9, -26.2, 0.8, 2.2, A.skinD)
  H(-3.9, -26.6, 3.5, 2.1, GLASSES); H(0.4, -26.6, 3.5, 2.1, GLASSES); H(-0.4, -26.2, 0.8, 0.5, GLASSES); H(-4.4, -26.2, 0.6, 0.5, GLASSES); H(3.8, -26.2, 0.6, 0.5, GLASSES)
  const glint = (t * 0.7) % 3
  if (glint < 1.2) { H(-3.4 + glint * 2, -26.3, 0.8, 0.5, '#FFD27A'); H(0.9 + glint * 2, -26.3, 0.6, 0.4, '#5CE1E6') }
  H(-1.1, -23.1, 2.2, 0.5, '#7A3A30'); H(4.2, -25.6, 0.5, 3.6, '#BFE6EA')
  if (id === 'rook') H(-1.8, -23.9, 3.6, 0.8, A.hair)
  if (A.mic) { H(-4.9, -24.6, 0.5, 2.2, '#41D6C3'); H(-4.9, -22.8, 2.8, 0.5, '#41D6C3') }
  const c = A.hair
  const hl = A.hl
  if (id === 'rook') { H(-4.3, -29.6, 8.6, 2.4, c); H(-4.3, -27.4, 0.9, 2.8, c); H(3.4, -27.4, 0.9, 2.8, c); H(-2.6, -29.6, 3, 0.6, hl) }
  if (id === 'bolt') { H(-4, -29.4, 8, 1.6, c); H(-4, -28, 0.6, 1.6, c); H(3.4, -28, 0.6, 1.6, c) }
  if (id === 'echo') { H(-4.8, -29.8, 9.6, 2.9, c); H(-4.8, -27, 1.5, 6.2, c); H(3.3, -27, 1.5, 6.2, c); H(-3.8, -27.2, 3.2, 1, c); H(-3, -29.8, 3, 0.6, hl); H(-4.6, -30.4, 9.2, 0.7, '#2A3A44') }
  if (id === 'pixel') { H(-4, -30.4, 8, 2.6, c); H(-1.6, -32.2, 5, 2, c); H(-1, -32.2, 2.2, 0.6, hl); H(-4, -28, 0.7, 1.6, c); H(3.3, -28, 0.7, 1.6, c) }
} // prettier-ignore
