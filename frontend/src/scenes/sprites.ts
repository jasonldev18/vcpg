// Build-crew pixel characters (DESIGN section 4.1), from MissionControl.dc.html's AGENTS.

export interface CrewSprite {
  id: string // the backend agent name
  name: string
  x: number // position on the 680 x 450 stage
  y: number
  b: string
  s: string
  h: string
  lid: string // the colour that closes the eyes when it blinks
  px: string[]
  doing: string // status word while working
}

export const PALETTE: Record<string, string> = {
  o: '#2E3A63',
  w: '#FFFFFF',
  p: '#10162B',
  k: '#FF8FA3',
  m: '#141A30',
  y: '#FFD45E',
  g: '#E8F1FF',
}

export const CREW: CrewSprite[] = [
  {
    id: 'planner', name: 'Planner', x: 340, y: 56, b: '#5AA9FF', s: '#2F6FD0', h: '#CFE5FF', lid: 'b', doing: 'planning',
    px: ['.....aa.....', '.....oo.....', '...oooooo...', '..obbbbbbo..', '.obbbbbbbbo.', '.obwpbbwpbo.', '.obwpbbwpbo.', '.okbbbbbbko.', '.obbbmmbbbo.', '..osbbbbso..', '...oooooo...', '...oo..oo...'],
  },
  {
    id: 'tutor', name: 'Tutor', x: 112, y: 108, b: '#6FD98A', s: '#3FA864', h: '#D9F7C9', lid: 'b', doing: 'teaching',
    px: ['.oooooooooo.', '...oooooo.y.', '..obbbbbboy.', '.obbbbbbbbo.', '.obwwbbwwbo.', '.obwpbbwpbo.', '.okbbyybbko.', '.obbbbbbbbo.', '.obhhhhhhbo.', '..obhhhhbo..', '...oooooo...', '...yy..yy...'],
  },
  {
    id: 'builder', name: 'Builder', x: 568, y: 108, b: '#FF9A52', s: '#D96A2A', h: '#FFD9B8', lid: 'b', doing: 'writing code',
    px: ['....yyyy....', '...yyyyyy...', '..yyyyyyyy..', '.oooooooooo.', '.obbbbbbbbo.', '.obwpbbwpbo.', '.obwpbbwpbo.', '.okbbbbbbko.', '.obbmmmmbbo.', '..osbbbbso..', '...oooooo...', '...oo..oo...'],
  },
  {
    id: 'interviewer', name: 'Interviewer', x: 84, y: 282, b: '#FF7EB6', s: '#D94A8C', h: '#FFD3E6', lid: 'b', doing: 'asking',
    px: ['...oooooo...', '..oaaaaaao..', '.oabbbbbbao.', '.oabbbbbbao.', 'aobwpbbwpboa', 'aobwpbbwpboa', 'aokbbbbbbko.', 'aaobbmmbbbo.', '.obbbbbbbbo.', '..osbbbbso..', '...oooooo...', '...oo..oo...'],
  },
  {
    id: 'reviewer', name: 'Reviewer', x: 596, y: 282, b: '#B58CFF', s: '#7F56D9', h: '#E5D6FF', lid: 'b', doing: 'reviewing',
    px: ['.oo......oo.', '.obo....obo.', '.obboooobbo.', '.obbbbbbbbo.', '.ogwpggwpgo.', '.obggbbggbo.', '.okbbbbbbko.', '.obbbmmbbbo.', '.obbbbbbbbo.', '..osbbbbso..', '...oooooo.oo', '...oo..oo.o.'],
  },
  {
    id: 'grader', name: 'Grader', x: 226, y: 366, b: '#41D6C3', s: '#1E9C8C', h: '#C9F7F0', lid: 'a', doing: 'scoring',
    px: ['.....yy.....', '....yyyy....', '...oooooo...', '..obbbbbbo..', '.oaaaaaaaao.', '.oawpaawpao.', '.okbbbbbbko.', '.obbbmmbbbo.', '.obbbbbbbbo.', '..osbbbbso..', '...oooooo...', '...oo..oo...'],
  },
  {
    id: 'slide_writer', name: 'Slide writer', x: 454, y: 366, b: '#FFD45E', s: '#D9A62A', h: '#FFF1C2', lid: 'm', doing: 'drafting',
    px: ['.oooooooooo.', '.ommmmmmmmo.', '.omwmmmmwmo.', '.omwmmmmwmo.', '.ommmaammmo.', '.ommmmmmmmo.', '.oooooooooo.', '....obbo....', '..obbbbbbo..', '..osbbbbso..', '...oooooo...', '...oo..oo...'],
  },
] // prettier-ignore

function colour(a: CrewSprite, ch: string, accent: string): string {
  if (ch === 'b') return a.b
  if (ch === 's') return a.s
  if (ch === 'h') return a.h
  if (ch === 'a') return accent
  return PALETTE[ch]
}

/** CSS box-shadow drawing the sprite at 5px per pixel; `lidOnly` paints closed eyes. */
export function spriteShadow(a: CrewSprite, accent: string, lidOnly = false): string {
  const out: string[] = []
  a.px.forEach((row, y) =>
    [...row].forEach((ch, x) => {
      if (ch === '.') return
      const eye = ch === 'w' || ch === 'p'
      if (lidOnly && !eye) return
      out.push(`${(x + 1) * 5}px ${(y + 1) * 5}px 0 ${colour(a, lidOnly ? a.lid : ch, accent)}`)
    }),
  )
  return out.join(', ')
}

/** Draw a sprite on a canvas at `size` px per pixel (the Squad portrait). */
export function drawSprite(
  g: CanvasRenderingContext2D,
  a: CrewSprite,
  ox: number,
  oy: number,
  size: number,
  blink: boolean,
  accent: string,
) {
  a.px.forEach((row, r) =>
    [...row].forEach((ch, c) => {
      if (ch === '.') return
      const k = blink && (ch === 'w' || ch === 'p') ? a.lid : ch
      g.fillStyle = colour(a, k, accent)
      g.fillRect(ox + c * size, oy + r * size, size, size)
      g.fillStyle = 'rgba(255,255,255,0.08)'
      g.fillRect(ox + c * size, oy + r * size, size, 2)
    }),
  )
}
