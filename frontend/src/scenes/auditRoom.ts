// The audit bay: a full-screen pixel mission-control room (DESIGN 5.1), ported from
// design/prototypes/Audit.dc.html. The choreography (agents walking, pinning, repairing,
// testing) is ambient animation per mode; the board cards, the mode and the siren come from
// the real audit state.

export type Mode = 'offline' | 'quick' | 'deep'
type AgentId = 'lead' | 'build' | 'teach' | 'out'
type Face = 'back' | 'front' | 'left' | 'right'

export interface IssueCard {
  key: string
  id: string
  tag: string
  title: string
  state: 'open' | 'repair' | 'fixed'
}

export interface PrCard {
  key: string
  id: string
  tag: string
  title: string
  state: 'tests' | 'ready' | 'merged'
  url: string | null
}

export type Picked =
  | { kind: 'issue'; card: IssueCard }
  | { kind: 'pr'; card: PrCard }
  | { kind: 'agent'; name: string }

interface Crew {
  name: string
  role: string
  code: string
  tie: string
  tieD: string
  skin: string
  skinD: string
  hair: string
  hl: string
  home: string
  coat?: boolean
  mic?: boolean
  pocket?: string
}

interface Loc {
  p: [number, number]
  via: [number, number][]
  face: Face
  sit?: boolean
}

type Step =
  | { type: 'go'; to: string; run?: boolean; pts?: [number, number][]; el?: number }
  | { type: 'work'; secs: number; say: string; anim: string; at?: string; fx?: string; el?: number }
  | { type: 'until'; n: number; say: string; anim: string; at?: string; el?: number }
  | { type: 'ev'; ev: string; el?: number }
  | { type: 'emote'; e: string; secs: number; el?: number }
  | { type: 'carry'; c: string | null; el?: number }

interface Agent {
  id: AgentId
  u: number
  y: number
  loc: string
  seated: boolean
  walking: boolean
  face: Face
  anim: string
  say: string
  prevSay: string
  sayAt: number
  at: string | null
  fx: string | null
  carry: string | null
  emote: { e: string; from: number; until: number } | null
  poke: number
  off: number
  front: boolean
  q: Step[]
  cur: Step | null
}

interface Part {
  x: number
  y: number
  vx: number
  vy: number
  g: number
  life: number
  c: string
  s: number
  floor: number
}

interface Text {
  t: string
  x: number
  y: number
  size: number
  color: string
  align?: CanvasTextAlign
  glow?: boolean
  clip?: [number, number, number, number]
  rot?: number
  box?: boolean
}

type Glow = [number, number, number, number, string]
type Ctx = CanvasRenderingContext2D

const CREW: Record<AgentId, Crew> = {
  lead: { name: 'ROOK', role: 'AUDIT LEAD', code: 'AGENT 001', tie: '#FF4D5E', tieD: '#B8303C', skin: '#E0B48F', skinD: '#C4936C', hair: '#C9CED6', hl: '#EEF0F4', home: 'seat_lead', coat: true },
  build: { name: 'BOLT', role: 'BUILD AUDITOR', code: 'AGENT 004', tie: '#5AA9FF', tieD: '#2F6FD0', skin: '#8D5A3B', skinD: '#6E4329', hair: '#2A1E16', hl: '#4A3A2E', home: 'seat_code' },
  teach: { name: 'ECHO', role: 'TEACHING AUDITOR', code: 'AGENT 007', tie: '#41D6C3', tieD: '#1E9C8C', skin: '#F1C7A3', skinD: '#D8A884', hair: '#1A1420', hl: '#3A2E48', home: 'seat_lessons', mic: true },
  out: { name: 'PIXEL', role: 'OUTPUT AUDITOR', code: 'AGENT 009', tie: '#FFD45E', tieD: '#D9A62A', skin: '#C68B5E', skinD: '#A56E45', hair: '#F2C25A', hl: '#FFE7A0', home: 'seat_slides', pocket: '#FFD45E' },
} // prettier-ignore
const HUB: [number, number] = [0, 262]
const LOC: Record<string, Loc> = {
  seat_code: { p: [-0.585, 252], via: [[-0.585, 262]], face: 'back', sit: true },
  seat_plans: { p: [-0.275, 252], via: [[-0.275, 262]], face: 'back', sit: true },
  seat_lessons: { p: [0.275, 252], via: [[0.275, 262]], face: 'back', sit: true },
  seat_inter: { p: [0.585, 252], via: [[0.585, 262]], face: 'back', sit: true },
  seat_slides: { p: [-0.42, 302], via: [[-0.42, 318], [0, 318]], face: 'back', sit: true },
  behind_slides: { p: [-0.42, 314], via: [[-0.42, 318], [0, 318]], face: 'back' },
  seat_lead: { p: [0, 357], via: [[0.28, 357], [0.28, 318], [0, 318]], face: 'back', sit: true },
  issue_a: { p: [-0.56, 216], via: [[0, 216]], face: 'back' }, issue_b: { p: [-0.44, 216], via: [[0, 216]], face: 'back' }, issue_c: { p: [-0.32, 216], via: [[0, 216]], face: 'back' },
  pr_a: { p: [0.32, 216], via: [[0, 216]], face: 'back' }, pr_b: { p: [0.44, 216], via: [[0, 216]], face: 'back' }, pr_c: { p: [0.56, 216], via: [[0, 216]], face: 'back' },
  bench_a: { p: [0.8, 232], via: [[0.8, 262]], face: 'right' }, bench_b: { p: [0.8, 244], via: [[0.8, 262]], face: 'right' }, bench_c: { p: [0.8, 256], via: [[0.8, 262]], face: 'right' },
  test_a: { p: [-0.8, 232], via: [[-0.8, 262]], face: 'left' }, test_b: { p: [-0.8, 244], via: [[-0.8, 262]], face: 'left' }, test_c: { p: [-0.8, 256], via: [[-0.8, 262]], face: 'left' },
} // prettier-ignore
const DESKS = [
  { yF: 240, u0: -0.74, u1: -0.12, st: [['code', -0.74, -0.43, ['code', 'tree']], ['plans', -0.43, -0.12, ['gantt', 'list']]] },
  { yF: 240, u0: 0.12, u1: 0.74, st: [['lessons', 0.12, 0.43, ['quiz', 'bars']], ['interviews', 0.43, 0.74, ['wave', 'chat']]] },
  { yF: 290, u0: -0.64, u1: -0.2, st: [['slides', -0.64, -0.2, ['slide', 'thumbs', 'chart']]] },
  { yF: 290, u0: 0.2, u1: 0.64, st: [['comms', 0.2, 0.64, ['radar', 'map']]] },
  { yF: 345, u0: -0.2, u1: 0.2, st: [['holo', -0.2, 0.2, ['list', 'globe', 'map']]] },
  { yF: 345, u0: -1.0, u1: -0.45, st: [['decorL', -1.0, -0.45, ['chart', 'radar']]] },
  { yF: 345, u0: 0.45, u1: 1.0, st: [['decorR', 0.45, 1.0, ['map', 'bars']]] },
] as { yF: number; u0: number; u1: number; st: [string, number, number, string[]][] }[] // prettier-ignore
const LABEL: Record<string, string> = {
  code: 'CODE',
  plans: 'PLANS',
  lessons: 'LESSONS',
  interviews: 'INTERVIEWS',
  slides: 'SLIDES',
  comms: 'COMMS',
  holo: 'COMMAND',
  decorL: 'NAV',
  decorR: 'SIGNALS',
}
const CHAIRS: [string, number, number][] = [['seat_code', -0.585, 252], ['seat_plans', -0.275, 252], ['seat_lessons', 0.275, 252], ['seat_inter', 0.585, 252], ['seat_slides', -0.42, 302], ['seat_comms', 0.42, 302], ['seat_lead', 0, 357]] // prettier-ignore

const hw = (y: number) => (260 * (y - 60)) / 140
const X = (u: number, y: number) => 360 + u * hw(y)
const sc = (y: number) => hw(y) / 260
const hs = (n: number) => {
  const v = Math.sin(n * 127.1 + 311.7) * 43758.5453
  return v - Math.floor(v)
}
const yt = (x: number) => 60 - 0.14615 * Math.abs(360 - x)
const yb = (x: number) => 60 + 0.53846 * Math.abs(360 - x)

function poly(g: Ctx, pts: number[][], fill: string) {
  g.fillStyle = fill
  g.beginPath()
  pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])))
  g.closePath()
  g.fill()
}

function rect(g: Ctx, x: number, y: number, w: number, h: number, c: string) {
  g.fillStyle = c
  g.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h)))
}

function scripts(mode: Mode): Record<AgentId, Step[]> {
  const go = (to: string, run?: boolean): Step => ({ type: 'go', to, run })
  const work = (secs: number, say: string, anim?: string, at?: string, fx?: string): Step => ({ type: 'work', secs, say, anim: anim || 'type', at, fx })
  const ev = (e: string): Step => ({ type: 'ev', ev: e })
  const emo = (e: string, secs: number): Step => ({ type: 'emote', e, secs })
  const carry = (c: string | null): Step => ({ type: 'carry', c })
  const rest = () => work(1e9, '', 'idle')
  const sleep = () => work(1e9, '', 'sleep')
  const fix = (k: number, iss: string, bench: string, test: string, pr: string, fixSay: string, testSay: string, extra: Step[] = []): Step[] => [
    emo('!', 0.7), go(iss, true), work(1, 'PINNING INTEL', 'pin'), ev('pin:' + k), work(0.5, '', 'idle'),
    carry('issue'), ev('take:' + k), go(bench), carry(null), ev('fix:' + k), work(4.2, fixSay, 'hammer', 'bench', 'spark'), carry('pr'), go(test), carry(null),
    work(2.5, testSay, 'scan', 'test'), ...extra, carry('pr'), go(pr), work(0.8, '', 'pin'), carry(null), ev('pr:' + k), work(1.4, '', 'cheer'),
  ]
  if (mode === 'offline') return { lead: [sleep()], build: [sleep()], teach: [sleep()], out: [sleep()] }
  if (mode === 'quick')
    return {
      build: [sleep()], teach: [sleep()], out: [sleep()],
      lead: [work(1.3, '', 'stretch'), go('seat_inter'), work(2.4, 'CHECKING ANSWERS', 'type', 'interviews'), go('behind_slides'), work(2.8, 'CHECKING SLIDES', 'type', 'slides'),
        ...fix(1, 'issue_b', 'bench_b', 'test_b', 'pr_b', 'FIXING', 'RUNNING TESTS'), ev('ready'), go('seat_lead'), work(2.4, 'SCAN COMPLETE', 'idle'), ev('done'), rest()],
    }
  return {
    lead: [work(1.3, '', 'stretch'), work(5, 'COLLECTING REPORTS', 'type', 'holo'), { type: 'until', n: 3, say: 'TRACING CAUSES', anim: 'type', at: 'holo' },
      emo('!', 0.6), go('pr_b', true), work(1.8, 'STAMPING APPROVAL', 'pin'), ev('ready'), work(1.6, '', 'cheer'), go('seat_lead'), work(2.6, 'SCAN COMPLETE', 'idle'), ev('done'), rest()],
    build: [work(1.0, '', 'stretch'), work(3, 'CHECKING CODE', 'type', 'code'), emo('ok', 0.6), go('seat_plans'), work(3, 'CHECKING PLANS', 'type', 'plans'),
      ...fix(2, 'issue_a', 'bench_a', 'test_a', 'pr_a', 'FIXING', 'RUNNING TESTS'), go('seat_code'), rest()],
    teach: [work(1.5, '', 'stretch'), work(3, 'CHECKING QUIZZES', 'type', 'lessons'), emo('ok', 0.6), go('seat_inter'), work(3.6, 'READING TRANSCRIPTS', 'type', 'interviews'),
      ...fix(0, 'issue_b', 'bench_b', 'test_b', 'pr_c', 'FIXING', 'RERUNNING CALIBRATION'), go('seat_lessons'), rest()],
    out: [work(2.0, '', 'stretch'), work(4.2, 'CHECKING SLIDES', 'type', 'slides'),
      ...fix(1, 'issue_c', 'bench_c', 'test_c', 'pr_b', 'FIXING', 'RECHECKING SLIDES'), go('seat_slides'), rest()],
  }
} // prettier-ignore

export class AuditRoom {
  private buf = document.createElement('canvas')
  private texts: Text[] = []
  private post: ((g: Ctx) => void)[] = []
  private glows: Glow[] = []
  private hover: string | null = null
  private hoverCard: Picked | null = null
  private t = 0
  private mode: Mode = 'offline'
  private agents: Agent[] = []
  private parts: Part[] = []
  private beams: { x0: number; y0: number; x1: number; y1: number; c: string; t0: number }[] = []
  private alarmAt = -10
  private readyAt = -10
  private doneAt: number | null = null
  private shake = 0
  private pinned = 0
  private cleared = 0
  private cardT: Record<string, number> = {}
  issues: IssueCard[] = []
  prs: PrCard[] = []
  alarm = false
  private view: HTMLCanvasElement

  constructor(view: HTMLCanvasElement) {
    this.view = view
    this.buf.width = 720
    this.buf.height = 405
    this.reset('offline')
  }

  setMode(mode: Mode) {
    if (mode !== this.mode) this.reset(mode)
  }

  /** A high-severity issue landed: siren and a brief screen shake (DESIGN 5.1). */
  siren() {
    this.alarmAt = this.t
    this.shake = 0.5
  }

  setBoards(issues: IssueCard[], prs: PrCard[]) {
    for (const c of [...issues, ...prs]) if (!(c.key in this.cardT)) this.cardT[c.key] = this.t
    this.issues = issues.slice(0, 3)
    this.prs = prs.slice(0, 3)
  }

  private reset(mode: Mode) {
    const sc0 = scripts(mode)
    this.mode = mode
    this.t = 0
    this.alarmAt = -10
    this.readyAt = -10
    this.doneAt = null
    this.shake = 0
    this.parts = []
    this.beams = []
    this.pinned = 0
    this.cleared = 0
    this.agents = (['lead', 'build', 'teach', 'out'] as AgentId[]).map((id, i) => {
      const L = LOC[CREW[id].home]
      return {
        id, u: L.p[0], y: L.p[1], loc: CREW[id].home, seated: true, walking: false, face: 'back', anim: 'sleep', say: '', prevSay: '', sayAt: 0,
        at: null, fx: null, carry: null, emote: null, poke: -10, off: i * 0.73, front: id === 'out' && mode !== 'deep', q: sc0[id].slice(), cur: null,
      } // prettier-ignore
    })
  }

  private burst(
    x: number,
    y: number,
    n: number,
    cols: string[],
    spread: number,
    up: number,
    floor = 400,
  ) {
    for (let i = 0; i < n; i++)
      this.parts.push({
        x,
        y,
        vx: (Math.random() - 0.5) * spread,
        vy: -up * (0.4 + Math.random() * 0.8),
        g: 160,
        life: 0.9 + Math.random() * 0.9,
        c: cols[i % cols.length],
        s: Math.random() < 0.3 ? 2 : 1,
        floor,
      })
  }

  private fire(ev: string, a: Agent) {
    const k = ev.split(':')[0]
    if (k === 'pin') {
      this.beams.push({
        x0: 360,
        y0: 94,
        x1: 181,
        y1: 70 + (this.pinned++ % 3) * 31,
        c: '255,77,94',
        t0: this.t,
      })
    }
    if (k === 'pr') {
      this.beams.push({
        x0: 360,
        y0: 94,
        x1: 539,
        y1: 70 + (this.cleared++ % 3) * 31,
        c: '92,225,230',
        t0: this.t,
      })
      this.burst(X(a.u, a.y), a.y - 40, 14, ['#5CE1E6', '#FFFFFF'], 60, 70, a.y)
    }
    if (k === 'ready') {
      this.readyAt = this.t
      this.burst(
        539,
        90,
        70,
        ['#FFD27A', '#FF9B3D', '#FF4D5E', '#5CE1E6', '#FFFFFF'],
        160,
        120,
        216,
      )
    }
    if (k === 'done') this.doneAt = this.t
  }

  private route(fromKey: string, toKey: string): [number, number][] {
    const F = LOC[fromKey]
    const T = LOC[toKey]
    const fl = F && F.via.length ? F.via[F.via.length - 1] : null
    const tl = T.via.length ? T.via[T.via.length - 1] : null
    const sameAisle = fl && tl && Math.abs(fl[1] - tl[1]) < 1e-6
    const pts: [number, number][] = [
      ...(F ? F.via : []),
      ...(sameAisle ? [] : [HUB]),
      ...T.via.slice().reverse(),
      T.p,
    ].map((p) => [p[0], p[1]])
    const eq = (p: number[], q: number[]) =>
      Math.abs(p[0] - q[0]) < 1e-6 && Math.abs(p[1] - q[1]) < 1e-6
    let changed = true
    while (changed) {
      changed = false
      for (let i = 1; i < pts.length; i++)
        if (eq(pts[i], pts[i - 1])) {
          pts.splice(i, 1)
          changed = true
          break
        }
      for (let i = 1; i < pts.length - 1 && !changed; i++)
        if (eq(pts[i - 1], pts[i + 1])) {
          pts.splice(i, 2)
          changed = true
        }
    }
    return pts
  }

  private step(dt: number) {
    this.t += dt
    this.shake = Math.max(0, this.shake - dt)
    if (this.doneAt !== null && this.t - this.doneAt > 8) {
      this.reset(this.mode) // the scan loops while the real run is still going
      return
    }
    for (const a of this.agents) {
      if (!a.cur) {
        a.cur = a.q.shift() || null
        if (a.cur) a.cur.el = 0
      }
      const c = a.cur
      if (c) {
        if (c.type === 'go') {
          if (!c.pts) {
            c.pts = this.route(a.loc, c.to)
            a.seated = false
          }
          a.walking = true
          a.say = ''
          a.at = null
          a.fx = null
          const tp = c.pts[0]
          const sx = X(a.u, a.y)
          const tx = X(tp[0], tp[1])
          const dx = tx - sx
          const dy = tp[1] - a.y
          const d = Math.sqrt(dx * dx + dy * dy)
          const sp = (c.run ? 70 : 46) * sc(a.y) * dt
          if (d > 0.01)
            a.face =
              Math.abs(dy) > Math.abs(dx) * 0.6
                ? dy > 0
                  ? 'front'
                  : 'back'
                : dx > 0
                  ? 'right'
                  : 'left'
          if (d <= sp) {
            a.u = tp[0]
            a.y = tp[1]
            c.pts.shift()
            if (!c.pts.length) {
              a.cur = null
              a.walking = false
              a.loc = c.to
              a.face = LOC[c.to].face
              a.seated = !!LOC[c.to].sit
              this.burst(X(a.u, a.y), a.y - 1, 4, ['#4A3A30', '#3A2A20'], 30, 18, a.y)
            }
          } else {
            const nx = sx + (dx / d) * sp
            const ny = a.y + (dy / d) * sp
            a.y = ny
            a.u = (nx - 360) / hw(ny)
          }
        } else if (c.type === 'work' || c.type === 'until') {
          a.walking = false
          a.anim = c.anim || 'type'
          a.say = c.say || ''
          a.at = c.at || null
          a.fx = c.type === 'work' ? c.fx || null : null
          c.el = (c.el ?? 0) + dt
          if (c.type === 'work' ? c.el >= c.secs : this.cleared >= c.n) {
            a.cur = null
            a.say = ''
            a.at = null
            a.fx = null
          }
        } else if (c.type === 'emote') {
          if (c.el === 0) a.emote = { e: c.e, from: this.t, until: this.t + c.secs }
          a.walking = false
          a.anim = 'idle'
          a.say = ''
          c.el = (c.el ?? 0) + dt
          if (c.el >= c.secs) a.cur = null
        } else if (c.type === 'carry') {
          a.carry = c.c
          a.cur = null
        } else {
          a.cur = null
          this.fire(c.ev, a)
        }
      }
      if (a.say !== a.prevSay) {
        a.prevSay = a.say
        a.sayAt = this.t
      }
      if (a.fx === 'spark' && Math.floor(this.t * 8) % 4 === 2 && Math.random() < 0.7) {
        const s = sc(a.y)
        const x = X(a.u, a.y) + 9 * s
        const y = a.y - 13 * s
        for (let n = 0; n < 3; n++)
          this.parts.push({
            x,
            y,
            vx: (Math.random() - 0.3) * 70,
            vy: -20 - Math.random() * 50,
            g: 220,
            life: 0.3 + Math.random() * 0.3,
            c: n ? '#FFD27A' : '#FFFFFF',
            s: 1,
            floor: a.y,
          })
      }
    }
    this.parts = this.parts.filter((p) => (p.life -= dt) > 0).slice(-320)
    for (const p of this.parts) {
      p.x += p.vx * dt
      p.y += p.vy * dt
      p.vy += p.g * dt
      if (p.y > p.floor) {
        p.y = p.floor
        p.vy *= -0.3
        p.vx *= 0.6
      }
    }
    this.beams = this.beams.filter((b) => this.t - b.t0 < 1.2)
  }

  // ---- the suited figure, with poses and side views (Audit.dc.html `fig`)

  private fig(g: Ctx, id: AgentId, x: number, y: number, s: number, view: Face, pose: string, T: number, o: { off?: number; carry?: string | null } = {}) {
    const A = CREW[id]
    const SUIT = '#1C1E27', SUITD = '#111218', SUITL = '#2E3140', PANTS = '#15161D', SHOE = '#07070B', SHIRT = '#ECECF2', GL = '#06060B'
    const side = view === 'left' || view === 'right'
    const R = (ux: number, uy: number, uw: number, uh: number, c: string) => {
      g.fillStyle = c
      const X0 = view === 'left' ? x - (ux + uw) * s : x + ux * s
      const px = Math.round(X0), py = Math.round(y + uy * s)
      g.fillRect(px, py, Math.max(1, Math.round(X0 + uw * s) - px), Math.max(1, Math.round(y + (uy + uh) * s) - py))
    }
    const off = o.off || 0
    const f = Math.floor(T * 8 + off * 3) % 4, walk = pose === 'walk'
    const seated = /^sit|^sleep/.test(pose), sleeping = /^sleep/.test(pose), frontSeat = pose === 'sitFront' || pose === 'sleepFront'
    const dy = seated ? 7 : 0
    let L = 0
    if (walk) L = (f % 2) * 0.6
    if (pose === 'cheer') L = Math.abs(Math.sin((T * 2.4 + off) * Math.PI)) * 5
    const breathe = pose === 'idle' || pose === 'sit' || sleeping ? (Math.floor(T * 1.2 + off) % 2) * 0.4 : 0
    if (!seated) R(-6.5, -0.6, 13, 1.2, 'rgba(0,0,0,0.38)')
    if (frontSeat) {
      R(-6.5, -23, 13, 14, '#2A1C14'); R(-6.5, -23, 13, 0.8, '#FF9B3D'); R(-6.5, -23, 0.8, 14, '#3A2A1E'); R(-7, -9, 14, 2, '#1E140E')
      R(-0.6, -7, 1.2, 4, '#3A3F4C'); R(-5, -2.5, 10, 1, '#2A2E38')
    }
    const U = (ux: number, uy: number, uw: number, uh: number, c: string) => R(ux, uy + dy - L, uw, uh, c)
    if (!seated) {
      if (side) {
        const sw = walk ? [1.6, 0.5, -1.6, 0.5][f] : 0
        U(-1.6 - sw, -10, 3, 8.6, '#0F1016'); U(-1.6 + sw, -10, 3, 8.6, PANTS)
        U(-1.6 - sw, -1.5, 4.2, 1.5, SHOE); U(-1.6 + sw, -1.5, 4.2, 1.5, SHOE); U(1.2 + sw, -1.5, 1, 0.5, '#3A3F4C')
      } else {
        const ll = walk && f === 1 ? 0.9 : 0, rl = walk && f === 3 ? 0.9 : 0
        U(-4, -10 - ll, 3, 8.6, PANTS); U(1, -10 - rl, 3, 8.6, PANTS); U(-2.6, -10 - ll, 0.5, 8, '#20212B'); U(2.4, -10 - rl, 0.5, 8, '#20212B')
        U(-4.6, -1.5 - ll, 3.8, 1.5, SHOE); U(0.8, -1.5 - rl, 3.8, 1.5, SHOE); U(-4, -1.5 - ll, 1, 0.5, '#3A3F4C'); U(1.4, -1.5 - rl, 1, 0.5, '#3A3F4C')
      }
    } else if (frontSeat) {
      R(-4.2, -8.5, 3.2, 3, PANTS); R(1, -8.5, 3.2, 3, PANTS); R(-4.2, -5.5, 3.2, 4.5, '#111218'); R(1, -5.5, 3.2, 4.5, '#111218')
      R(-4.8, -1.5, 3.8, 1.5, SHOE); R(0.8, -1.5, 3.8, 1.5, SHOE)
    }
    if (A.coat && !seated && !side) { U(-6.3, -12, 12.6, 4, SUIT); U(-0.3, -12, 0.6, 4, SUITD) }
    if (side) {
      U(-3.6, -20, 7.2, 10.6, SUIT); U(-3.6, -20, 1, 10.6, SUITD); U(2.6, -20, 1, 4.6, SHIRT); U(3.0, -19.3, 0.7, 6.5, A.tie); U(-3.6, -10, 7.2, 0.6, SUITD)
      if (A.coat) U(-4, -12, 8, 3.5, SUIT)
    } else if (view === 'back' && !frontSeat) {
      U(-5.6, -20, 11.2, 10.6, SUIT); U(-0.25, -20, 0.5, 10.6, SUITD); U(-5.6, -20, 1, 10.6, SUITL); U(4.6, -20, 1, 10.6, SUITD); U(-1.6, -20.6, 3.2, 0.7, SHIRT)
    } else {
      U(-5.6, -20, 11.2, 10.6, SUIT); U(3.6, -20, 2, 10.6, SUITD); U(-5.6, -20, 1, 10.6, SUITL)
      U(-1.6, -20, 3.2, 4.6, SHIRT); U(-1, -15.4, 2, 1.4, SHIRT); U(-2.7, -20, 1.1, 5.6, SUITL); U(1.6, -20, 1.1, 5.6, SUITL)
      U(-0.5, -19.3, 1, 7.4, A.tie); U(-0.7, -19.8, 1.4, 1, A.tieD); U(-0.3, -11.8, 0.6, 0.6, '#3A3D4A'); U(-0.3, -13.6, 0.6, 0.6, '#3A3D4A')
      if (A.pocket) U(2.3, -18.2, 1.5, 0.9, A.pocket)
    }
    const arm = (ux: number, uy: number, uw: number, uh: number, hand: boolean) => { U(ux, uy, uw, uh, SUIT); U(ux, uy, Math.min(uw, 0.6), uh, SUITL); if (hand) U(ux, uy + uh - 0.2, uw, 1.6, A.skin) }
    const sw = walk ? (f < 2 ? 0.9 : -0.9) : 0
    if (side) {
      if (pose === 'hammer') {
        if (f < 2) { arm(0.2, -27, 2.2, 8, false); U(0.2, -28.6, 2.2, 1.6, A.skin); U(-1.4, -31.4, 5.4, 2.6, '#9AA3B5'); U(0.8, -29, 1, 1.2, '#6B4A3A') }
        else { arm(0, -18.4, 6.4, 2.2, false); U(6.2, -18.6, 1.6, 2.4, A.skin); U(7, -22, 2.6, 5.6, '#9AA3B5') }
      } else if (pose === 'scan') { arm(0, -17.6, 5.4, 2.2, false); U(5.2, -17.8, 1.4, 2.2, A.skin); U(5.8, -20.6, 2.6, 4.4, '#0E2A2C'); U(6.2, -20, 1.8, 3.2, Math.floor(T * 4) % 2 ? '#5CE1E6' : '#2A8A8E') }
      else arm(-1 + sw * 1.4, -19.6, 2.3, 9.2, true)
    } else if (pose === 'pin') { arm(-7.6, -19.6, 2, 9.6, true); arm(5.6, -29, 2, 9.4, false); U(5.6, -30.4, 2, 1.6, A.skin) }
    else if (pose === 'cheer') { arm(-8.6, -29, 2, 9.4, false); arm(6.6, -29, 2, 9.4, false); U(-8.6, -30.4, 2, 1.6, A.skin); U(6.6, -30.4, 2, 1.6, A.skin) }
    else if (pose === 'stretch' || pose === 'sitStretch') { arm(-9.4, -30, 2, 10.6, false); arm(7.4, -30, 2, 10.6, false); U(-9.4, -31.4, 2, 1.6, A.skin); U(7.4, -31.4, 2, 1.6, A.skin) }
    else if (pose === 'sit') { const k = (Math.floor(T * 6 + off) % 2) * 0.5; arm(-7.8, -19.4 + k, 2.2, 6, true); arm(5.6, -19.4 + (0.5 - k), 2.2, 6, true) }
    else if (sleeping && !frontSeat) { arm(-7.4, -18.6, 2, 7, true); arm(5.4, -18.6, 2, 7, true) }
    else { arm(-7.6, -19.6 + sw, 2, 9.6, true); arm(5.6, -19.6 - sw, 2, 9.6, true) }
    if (o.carry && (walk || pose === 'idle')) {
      const cc = o.carry === 'issue' ? '#D9B26A' : '#0E2A2C', cx = side ? 1.2 : 5.2
      U(cx, -14.6, 4.6, 5.8, cc); U(cx + 0.4, -14, 3.8, 0.6, o.carry === 'issue' ? '#B8862E' : '#5CE1E6')
      U(cx + 0.8, -12.4, 2.6, 1.2, o.carry === 'issue' ? '#FF4D5E' : '#5CE1E6')
    }
    const hx = sleeping && !frontSeat ? 1.4 : sleeping ? 0.8 : 0, hy = dy - L + breathe + (sleeping && !frontSeat ? 1.4 : 0)
    const H = (ux: number, uy: number, uw: number, uh: number, c: string) => R(ux + hx, uy + hy, uw, uh, c)
    H(-1.6, -21.8, 3.2, 1.8, A.skinD)
    if (side) {
      H(-3.6, -29, 7.2, 8, A.skin); H(3.4, -25.6, 0.9, 1.6, A.skin); H(-1.3, -26.2, 1.3, 2.2, A.skinD); H(-3.6, -21.6, 6, 0.8, A.skin)
      H(1, -26.6, 3.2, 2, GL); H(-1.1, -26.1, 2.2, 0.6, GL); H(2.6, -26.4, 0.7, 0.5, Math.floor(T * 1.5 + off) % 2 ? '#FFD27A' : '#5CE1E6')
      H(2.4, -23.1, 1.1, 0.5, '#7A3A30'); H(-1.6, -25.2, 0.5, 3.6, '#BFE6EA')
    } else if (view === 'back' && !frontSeat) {
      H(-4, -29, 8, 8, A.skin); H(-4.7, -26.2, 0.8, 2.2, A.skinD); H(3.9, -26.2, 0.8, 2.2, A.skinD)
      H(-4.4, -26.2, 0.5, 0.6, GL); H(3.9, -26.2, 0.5, 0.6, GL); H(4.1, -25, 0.5, 4.6, '#BFE6EA')
    } else {
      H(-4, -29, 8, 8, A.skin); H(-3.6, -21.6, 7.2, 0.8, A.skin); H(2.6, -28.6, 1.4, 7.2, A.skinD); H(-4.7, -26.2, 0.8, 2.2, A.skinD); H(3.9, -26.2, 0.8, 2.2, A.skinD)
      const gy = sleeping ? -25.6 : -26.6
      H(-3.9, gy, 3.5, 2.1, GL); H(0.4, gy, 3.5, 2.1, GL); H(-0.4, gy + 0.4, 0.8, 0.5, GL); H(-4.4, gy + 0.4, 0.6, 0.5, GL); H(3.8, gy + 0.4, 0.6, 0.5, GL)
      const gl = (T * 0.7 + off) % 3
      if (gl < 1.2) { H(-3.4 + gl * 2, gy + 0.3, 0.8, 0.5, '#FFD27A'); H(0.9 + gl * 2, gy + 0.3, 0.6, 0.4, '#5CE1E6') }
      if (sleeping) H(-0.6, -23.4, 1.2, 1, '#5A2A24')
      else if (pose === 'cheer') H(-1.4, -23.6, 2.8, 1.2, '#5A2A24')
      else H(-1.1, -23.1, 2.2, 0.5, '#7A3A30')
      if (id === 'lead') H(-1.8, -23.9, 3.6, 0.8, A.hair)
      H(4.2, -25.6, 0.5, 3.6, '#BFE6EA')
      if (A.mic) { H(-4.9, -24.6, 0.5, 2.2, '#41D6C3'); H(-4.9, -22.8, 2.8, 0.5, '#41D6C3') }
    }
    const c = A.hair, hl = A.hl
    if (id === 'lead') {
      if (side) { H(-3.8, -29.6, 6.4, 2.4, c); H(-3.8, -27.2, 2.6, 4.4, c); H(-0.6, -29.6, 2.6, 0.6, hl) }
      else if (view === 'back' && !frontSeat) { H(-4.3, -29.6, 8.6, 6.4, c); H(-3.6, -23.4, 7.2, 0.8, c); H(-1.2, -29.2, 2.4, 3, hl) }
      else { H(-4.3, -29.6, 8.6, 2.4, c); H(-4.3, -27.4, 0.9, 2.8, c); H(3.4, -27.4, 0.9, 2.8, c); H(-2.6, -29.6, 3, 0.6, hl) }
    }
    if (id === 'build') {
      if (side) { H(-3.6, -29.4, 6.2, 1.6, c); H(-3.6, -27.8, 2.2, 3, c) }
      else if (view === 'back' && !frontSeat) H(-4, -29.4, 8, 4.8, c)
      else { H(-4, -29.4, 8, 1.6, c); H(-4, -28, 0.6, 1.6, c); H(3.4, -28, 0.6, 1.6, c) }
    }
    if (id === 'teach') {
      if (side) { H(-4.1, -29.8, 6.9, 2.7, c); H(-4.1, -27.2, 3.4, 6.4, c); H(1.4, -27.4, 1.8, 1.2, c) }
      else if (view === 'back' && !frontSeat) { H(-4.8, -29.8, 9.6, 8.8, c); H(-2, -29.2, 4, 0.6, hl) }
      else { H(-4.8, -29.8, 9.6, 2.9, c); H(-4.8, -27, 1.5, 6.2, c); H(3.3, -27, 1.5, 6.2, c); H(-3.8, -27.2, 3.2, 1, c); H(-3, -29.8, 3, 0.6, hl) }
      H(-4.6, -30.4, 9.2, 0.7, '#2A3A44')
    }
    if (id === 'out') {
      if (side) { H(-3.6, -30.4, 6.8, 2.6, c); H(0.4, -32.2, 4.2, 2, c); H(-3.6, -28, 2.2, 3, c); H(1, -32.2, 2, 0.6, hl) }
      else if (view === 'back' && !frontSeat) { H(-4, -30.4, 8, 5.6, c); H(-1.6, -32.2, 5, 2, c) }
      else { H(-4, -30.4, 8, 2.6, c); H(-1.6, -32.2, 5, 2, c); H(-1, -32.2, 2.2, 0.6, hl); H(-4, -28, 0.7, 1.6, c); H(3.3, -28, 0.7, 1.6, c) }
    }
  } // prettier-ignore

  private chair(g: Ctx, x: number, y: number, s: number, lead: boolean) {
    const k = lead ? 1.18 : 1
    const R = (ux: number, uy: number, uw: number, uh: number, c: string) => rect(g, x + ux * s * k, y + uy * s * k, uw * s * k, uh * s * k, c)
    R(-6.4, -15.4, 12.8, 11.4, '#2A1C14'); R(-6.4, -15.4, 12.8, 0.8, lead ? '#FFD27A' : '#FF9B3D'); R(-6.4, -15.4, 0.8, 11.4, '#3A2A1E'); R(5.6, -15.4, 0.8, 11.4, '#1A120C')
    R(-4, -12, 8, 0.5, '#3A2A1E'); R(-4, -9, 8, 0.5, '#3A2A1E')
    R(-6.8, -5, 13.6, 1.6, '#1E140E'); R(-0.6, -3.6, 1.2, 2.6, '#3A3F4C'); R(-5.4, -1.2, 10.8, 1, '#2A2E38'); R(-5.6, -0.6, 1.2, 0.8, '#0B0B10'); R(4.4, -0.6, 1.2, 0.8, '#0B0B10')
  } // prettier-ignore

  private mon(g: Ctx, x: number, y: number, w: number, h: number, kind: string, on: boolean, T: number, offline: boolean, seed: number) {
    x = Math.round(x); y = Math.round(y); w = Math.max(4, Math.round(w)); h = Math.max(4, Math.round(h))
    g.fillStyle = '#0A0706'; g.fillRect(x - 1, y - 1, w + 2, h + 2)
    g.fillStyle = offline ? '#05060A' : on ? '#2C180A' : '#170E08'; g.fillRect(x, y, w, h)
    if (offline) {
      if (seed % 2 === 0) { const ph = Math.floor(T * 0.6), px = x + 1 + Math.floor(hs(ph + seed) * (w - 4)), py = y + 1 + Math.floor(hs(ph + seed + 9) * (h - 3)); g.fillStyle = '#24476E'; g.fillRect(px, py, 3, 1) }
      return
    }
    const al = on ? 1 : 0.42, col = (r: number, gg: number, b: number) => `rgba(${r},${gg},${b},${al})`
    const O1 = col(255, 155, 61), O2 = col(255, 210, 122), CY = col(92, 225, 230), RD = col(255, 77, 94), DM = col(122, 74, 32)
    const t = T * (on ? 1 : 0.2), R = (xx: number, yy: number, ww: number, hh: number, cc: string) => { g.fillStyle = cc; g.fillRect(Math.round(xx), Math.round(yy), Math.max(1, Math.round(ww)), Math.max(1, Math.round(hh))) }
    const rows = Math.floor((h - 2) / 2)
    if (kind === 'code') { const off = Math.floor(t * 6); for (let r = 0; r < rows; r++) { const n = off + r + seed * 13, ind = Math.floor(hs(n * 3) * 3) * 2; R(x + 2 + ind, y + 1 + r * 2, 2 + hs(n) * (w - 8 - ind), 1, n % 5 === 0 ? CY : n % 3 ? O1 : O2) } }
    if (kind === 'tree') { const cx = x + w / 2; R(cx - 1, y + 2, 3, 2, O2); R(x + w * 0.2, y + h * 0.45, w * 0.6, 1, DM); [0.2, 0.5, 0.8].forEach((p, i) => { R(x + w * p, y + 4, 1, h * 0.45 - 4 + 1, DM); R(x + w * p - 1, y + h * 0.5, 3, 2, i === Math.floor(t * 1.5) % 3 ? CY : O1); R(x + w * p, y + h * 0.5 + 2, 1, h * 0.2, DM); R(x + w * p - 2, y + h * 0.75, 5, 2, O1) }) }
    if (kind === 'gantt') { for (let r = 0; r < Math.floor((h - 2) / 3); r++) { const s0 = hs(r + seed) * w * 0.45, ln = w * (0.25 + hs(r * 7 + seed) * 0.3), p = (t * 0.15 + r * 0.17) % 1; R(x + 2 + s0, y + 2 + r * 3, ln, 2, DM); R(x + 2 + s0, y + 2 + r * 3, ln * p, 2, r % 3 ? O1 : O2) } }
    if (kind === 'list') { for (let r = 0; r < Math.floor((h - 2) / 3); r++) { const n = r + Math.floor(t * 0.8) + seed; R(x + 2, y + 2 + r * 3, 2, 2, hs(n) > 0.75 ? RD : hs(n) > 0.4 ? CY : O2); R(x + 6, y + 2 + r * 3, 4 + hs(n * 5) * (w - 12), 1, DM) } }
    if (kind === 'quiz') { for (let r = 0; r < Math.floor((h - 2) / 3); r++) { const n = r + Math.floor(t) + seed; R(x + 2, y + 2 + r * 3, 2, 2, hs(n) > 0.4 ? O2 : DM); R(x + 6, y + 2 + r * 3, 6 + hs(n * 3) * (w - 14), 1, O1) } }
    if (kind === 'bars') { const n = Math.floor((w - 2) / 4); for (let i = 0; i < n; i++) { const hh = (0.25 + 0.7 * Math.abs(Math.sin(t * 2 + i * 0.7 + seed))) * (h - 3); R(x + 2 + i * 4, y + h - 1 - hh, 3, hh, i % 3 ? O1 : O2) } }
    if (kind === 'wave') { for (let xx = 1; xx < w - 1; xx++) { const yy = y + h / 2 + Math.sin(xx * 0.45 + t * 7) * (h / 3) * (0.4 + 0.6 * Math.abs(Math.sin(t * 1.3 + xx * 0.04))); R(x + xx, yy, 1, 1, CY) } R(x + 1, y + h / 2, w - 2, 1, DM) }
    if (kind === 'chat') { const off = Math.floor(t * 2); for (let r = 0; r < Math.floor((h - 2) / 4); r++) { const n = off + r + seed, left = n % 2 === 0, ln = 6 + hs(n) * (w * 0.5); R(left ? x + 2 : x + w - 2 - ln, y + 2 + r * 4, ln, 2, left ? O1 : CY) } }
    if (kind === 'slide') {
      const idx = on ? Math.floor(t / 1.1) % 3 : 0; R(x + 2, y + 2, w - 4, 2, O1)
      if (idx === 0) { R(x + 2, y + 6, w * 0.35, h - 9, DM); for (let r = 0; r < 3; r++) R(x + w * 0.45, y + 6 + r * 3, w * 0.45, 1, O2) }
      if (idx === 1) { for (let i = 0; i < 4; i++) { const hh = (0.3 + i * 0.18) * (h - 8); R(x + 3 + (i * (w - 6)) / 4, y + h - 2 - hh, (w - 6) / 4 - 2, hh, i === 2 ? RD : O1) } }
      if (idx === 2) { R(x + 3, y + 7, w - 6, 3, O2); R(x + 3, y + 12, w * 0.6, 1, DM); if (on && Math.floor(T * 4) % 2) { R(x + 2, y + 6, w - 4, 1, RD); R(x + 2, y + 11, w - 4, 1, RD) } }
    }
    if (kind === 'thumbs') { const hi = Math.floor(t * 2) % 6; for (let i = 0; i < 6; i++) { const cx = x + 2 + (i % 3) * ((w - 4) / 3), cy = y + 2 + Math.floor(i / 3) * ((h - 4) / 2); R(cx, cy, (w - 4) / 3 - 2, (h - 4) / 2 - 2, i === hi ? O2 : DM) } }
    if (kind === 'chart') { for (let xx = 1; xx < w - 1; xx++) { const v = 0.5 + 0.3 * Math.sin(xx * 0.18 + t * 2 + seed) + 0.12 * Math.sin(xx * 0.7 + t * 3); R(x + xx, y + h - 2 - v * (h - 4), 1, 1, xx > w * 0.7 ? CY : O2) } }
    if (kind === 'radar') {
      const cx = x + w / 2, cy = y + h / 2, r = Math.min(w, h) / 2 - 2
      for (let i = 0; i < 24; i++) { const an = (i / 24) * Math.PI * 2; R(cx + Math.cos(an) * r, cy + Math.sin(an) * r, 1, 1, DM) }
      const an = t * 3; for (let k = 0; k < r; k++) R(cx + Math.cos(an) * k, cy + Math.sin(an) * k, 1, 1, O2)
      for (let i = 0; i < 3; i++) { const ba = hs(i + seed) * 6.28, br = hs(i * 3 + seed) * r * 0.8, d = (((an - ba) % 6.28) + 6.28) % 6.28; if (d < 2) R(cx + Math.cos(ba) * br, cy + Math.sin(ba) * br, 2, 2, RD) }
    }
    if (kind === 'map') { for (let yy = 2; yy < h - 1; yy += 3) for (let xx = 2; xx < w - 1; xx += 3) if (hs(xx * 0.31 + yy * 1.7 + seed) > 0.55) R(x + xx, y + yy, 1, 1, DM); for (let i = 0; i < 3; i++) if (Math.floor(t * 2 + i) % 3 === 0) R(x + 3 + hs(i + seed * 2) * (w - 6), y + 3 + hs(i * 5 + seed) * (h - 6), 2, 2, i ? O2 : CY) }
    if (kind === 'globe') { const cx = x + w / 2, cy = y + h / 2, r = Math.min(w, h) / 2 - 2; for (let la = -60; la <= 60; la += 30) for (let lo = 0; lo < 360; lo += 30) { const a1 = (la * Math.PI) / 180, a2 = (lo * Math.PI) / 180 + t; if (Math.cos(a2) < 0) continue; R(cx + r * Math.cos(a1) * Math.sin(a2), cy - r * Math.sin(a1), 1, 1, O2) } }
    g.fillStyle = 'rgba(255,255,255,0.04)'; g.fillRect(x, y, w, 1)
  } // prettier-ignore

  private drawRoom(g: Ctx, T: number, offline: boolean, alarm: boolean, act: Record<string, boolean>) {
    poly(g, [[0, 0], [720, 0], [620, 22], [100, 22]], '#0C0806')
    ;[-0.62, 0, 0.62].forEach((k) => {
      const xa = (y: number, u: number) => 360 + (u * 260 * (60 - y)) / 38
      for (let seg = 0; seg < 4; seg++) {
        const y0 = seg * 5.5 + 0.5, y1 = y0 + 3.5
        poly(g, [[xa(y0, k - 0.07), y0], [xa(y0, k + 0.07), y0], [xa(y1, k + 0.07), y1], [xa(y1, k - 0.07), y1]], offline ? '#2A2622' : '#FFE9C8')
      }
    })
    poly(g, [[0, 7], [100, 22], [100, 200], [0, 254]], '#1A110B')
    poly(g, [[720, 7], [620, 22], [620, 200], [720, 254]], '#1D140D')
    for (let i = 0; i < 3; i++) {
      const xa = 6 + i * 31, xb = xa + 25
      poly(g, [[xa, yt(xa) + 10], [xb, yt(xb) + 10], [xb, yb(xb) - 6], [xa, yb(xa) - 6]], '#0E0F14')
      for (let r = 0; r < 12; r++) for (let c = 0; c < 4; c++) {
        const fx = xa + 4 + c * 5.5, top = yt(fx) + 16, bot = yb(fx) - 14, yy = top + ((bot - top) * r) / 11
        const on = Math.floor(T * 2.2 + r * 1.3 + c * 2.1 + i) % 5 === 0
        g.fillStyle = on ? (c % 2 ? '#FF9B3D' : '#5BD68A') : '#1E2A22'; g.fillRect(Math.round(fx), Math.round(yy), 2, 1)
      }
    }
    this.texts.push({ t: 'SERVERS', x: 16, y: 44, size: 11, color: offline ? '#4A5266' : '#7A8CA8' })
    for (let i = 0; i < 2; i++) {
      const xa = 626 + i * 26, xb = xa + 22
      poly(g, [[xa, yt(xa) + 18], [xb, yt(xb) + 18], [xb, yb(xb) - 40], [xa, yb(xa) - 40]], '#2A2E38')
      const mid = (yt(xa) + yb(xa)) / 2
      poly(g, [[xa, mid - 4], [xb, mid - 7], [xb, mid - 3], [xa, mid]], '#E8B020')
      g.fillStyle = '#14100C'; g.fillRect(xa + 3, Math.round(mid - 3), 2, 1)
    }
    poly(g, [[680, yt(680) + 30], [716, yt(716) + 30], [716, yb(716) - 70], [680, yb(680) - 70]], '#2A1E14')
    for (let i = 0; i < 6; i++) { const xx = 684 + (i % 3) * 11, yy = yt(xx) + 38 + Math.floor(i / 3) * 18; g.fillStyle = '#9AA3B5'; g.fillRect(xx, yy, 6, 2); g.fillRect(xx + 2, yy, 2, 8) }
    this.texts.push({ t: 'REPAIR', x: 652, y: 44, size: 12, color: offline ? '#4A5266' : '#FFB45E', glow: !offline })
    this.texts.push({ t: 'ARCHIVE', x: 628, y: 66, size: 11, color: '#8A6A50' })
    g.fillStyle = '#17100B'; g.fillRect(100, 22, 520, 178)
    g.fillStyle = '#0B0807'; g.fillRect(104, 24, 512, 11)
    g.fillStyle = '#1E140E'; g.fillRect(104, 24, 70, 11); g.fillRect(546, 24, 70, 11)
    const tt = Math.floor(this.t), mm = String(Math.floor(tt / 60)).padStart(2, '0'), ss = String(tt % 60).padStart(2, '0')
    this.texts.push({ t: offline ? 'T+ --:--' : `T+ ${mm}:${ss}`, x: 108, y: 33, size: 11, color: offline ? '#4A5266' : '#FFD27A' })
    const awake = this.agents.filter((a) => a.anim !== 'sleep').length
    this.texts.push({ t: `${awake}/4 ON DUTY`, x: 550, y: 33, size: 11, color: awake ? '#5CE1E6' : '#4A5266' })
    this.texts.push({ t: `CLASSIFIED // OPERATION AUDIT // EYES ONLY // ${offline ? 'BAY DARK, AGENTS RESTING // ' : alarm ? 'INTEL PINNED, SIREN ACTIVE // ' : 'SWEEP IN PROGRESS // '}VCPG CONTROL //`, x: 540 - ((T * 26) % 720), y: 33, size: 11, color: alarm ? '#FF7A84' : '#BFA58F', clip: [180, 24, 362, 12] })
    ;[254, 458].forEach((px) => { g.fillStyle = '#22170F'; g.fillRect(px, 36, 8, 162); g.fillStyle = offline ? '#2A1C10' : Math.floor(T * 3 + px) % 4 === 0 ? '#FFD27A' : '#7A4A20'; g.fillRect(px + 3, 40, 2, 154) })
    this.drawIssueBoard(g, T, alarm, offline)
    this.drawPrBoard(g, T, offline)
    this.drawGlobe(g, T, alarm, offline, act)
    ;[['radar', 'comms'], ['code', 'code'], ['wave', 'interviews'], ['slide', 'slides'], ['bars', 'test'], ['gantt', 'plans']].forEach((p, i) => {
      this.mon(g, 106 + i * 86, 158, 80, 34, p[0], !!act[p[1]], T, offline, i + 3)
      if (!offline) this.glows.push([146 + i * 86, 175, 50, act[p[1]] ? 0.16 : 0.05, '255,155,61'])
    })
    g.fillStyle = '#22170F'; g.fillRect(100, 196, 520, 4)
    poly(g, [[100, 200], [620, 200], [720, 254], [720, 405], [0, 405], [0, 254]], '#120C09')
    g.strokeStyle = 'rgba(255,155,61,0.07)'; g.lineWidth = 1; g.beginPath()
    for (let u = -1; u <= 1.001; u += 0.125) { g.moveTo(X(u, 200), 200); g.lineTo(X(u, 405), 405) }
    ;[208, 218, 230, 245, 262, 282, 306, 335, 370].forEach((yy) => { g.moveTo(0, yy); g.lineTo(720, yy) })
    g.stroke()
    g.globalCompositeOperation = 'lighter'
    const refl: [number, number, string][] = [[110, 252, offline ? '60,90,140' : alarm ? '255,60,70' : '255,77,94'], [264, 456, offline ? '60,90,140' : '255,160,70'], [468, 610, '92,225,230']]
    refl.forEach((r) => { const gr = g.createLinearGradient(0, 200, 0, 262); gr.addColorStop(0, `rgba(${r[2]},0.10)`); gr.addColorStop(1, `rgba(${r[2]},0)`); g.fillStyle = gr; g.fillRect(r[0], 200, r[1] - r[0], 62) })
    ;[-0.11, 0.11].forEach((u) => {
      ;[212, 228, 248, 272, 300, 332, 368].forEach((yy, i) => {
        const ph = (T * 1.6 - i * 0.18) % 1, on = ph < 0.25 && !offline, s = sc(yy)
        g.fillStyle = on ? 'rgba(255,190,90,0.9)' : offline ? 'rgba(255,120,40,0.15)' : 'rgba(255,155,61,0.3)'
        g.fillRect(Math.round(X(u, yy) - s), Math.round(yy), Math.max(1, Math.round(2 * s)), 1)
      })
    })
    if (!offline) [-0.62, 0, 0.62].forEach((k) => { const x0 = 360 + k * 260; poly(g, [[x0 - 14, 22], [x0 + 14, 22], [x0 + 70, 200], [x0 - 70, 200]], 'rgba(255,230,190,0.025)') })
    g.globalCompositeOperation = 'source-over'
  } // prettier-ignore

  private slam(key: string) {
    const since = this.t - (this.cardT[key] ?? -10)
    return since < 0.2 ? 1 - since / 0.2 : 0
  }

  private drawIssueBoard(g: Ctx, T: number, alarm: boolean, offline: boolean) {
    const x0 = 110, y0 = 40, w = 142, h = 112
    rect(g, x0 - 2, y0 - 2, w + 4, h + 4, '#0A0706'); rect(g, x0, y0, w, h, offline ? '#0C0809' : '#1A0C0C')
    rect(g, x0, y0, w, 13, alarm ? (Math.floor(T * 4) % 2 ? '#9A1E2A' : '#5A141C') : offline ? '#2A1416' : '#4A1A1E')
    this.texts.push({ t: 'INTEL // ISSUES', x: x0 + 5, y: y0 + 10, size: 12, color: '#FFD0D4' })
    this.issues.forEach((card, i) => {
      const st = card.state, slam = this.slam(card.key)
      const cx = x0 + 5 - slam * 8, cy = y0 + 17 + i * 31 - slam * 3, cw = w - 10 + slam * 16, ch = 27 + slam * 6
      const fill = st === 'open' ? '#4A1218' : st === 'repair' ? '#2E200E' : '#122018'
      const acc = st === 'open' ? (Math.floor(T * 5) % 2 ? '#FF4D5E' : '#8A1E28') : st === 'repair' ? '#FFD27A' : '#5BD68A'
      if (st === 'open') rect(g, cx - 1, cy - 1, cw + 2, ch + 2, acc)
      rect(g, cx, cy, cw, ch, offline ? '#0E1210' : fill); rect(g, cx, cy, 3, ch, acc)
      rect(g, cx + cw - 7, cy + 4, 3, 3, st === 'open' ? (Math.floor(T * 6) % 2 ? '#FFFFFF' : '#FF4D5E') : acc)
      const col = st === 'open' ? '#FFD0D4' : st === 'repair' ? '#FFE3A8' : '#9FD8AE'
      this.texts.push({ t: `${card.id} ${card.tag}`.slice(0, 22), x: cx + 7, y: cy + 11, size: 12, color: offline ? '#5E7A66' : col })
      this.texts.push({ t: st === 'open' ? 'OPEN' : st === 'repair' ? 'IN REPAIR' : 'FIXED', x: cx + 7, y: cy + 22, size: 11, color: offline ? '#4A5E50' : col })
    })
    if (!this.issues.length) this.texts.push({ t: 'NO INTEL PINNED', x: x0 + w / 2, y: y0 + 64, size: 11, color: '#7A4A4E', align: 'center' })
    ;[x0 + 10, x0 + w - 10].forEach((bx, i) => {
      rect(g, bx - 4, y0 - 5, 8, 3, '#2A1C14')
      const on = alarm && Math.floor(T * 6 + i) % 2
      rect(g, bx - 3, y0 - 9, 6, 4, alarm ? (on ? '#FF4D5E' : '#FF9AA2') : '#3A2A26'); rect(g, bx - 2, y0 - 10, 4, 1, alarm ? '#FFD0D4' : '#4A3A30')
    })
    if (!offline) this.glows.push([x0 + w / 2, y0 + h / 2, 90, alarm ? 0.3 : 0.1, '255,60,70'])
  } // prettier-ignore

  private drawPrBoard(g: Ctx, T: number, offline: boolean) {
    const x0 = 468, y0 = 40, w = 142, h = 112
    rect(g, x0 - 2, y0 - 2, w + 4, h + 4, '#0A0706'); rect(g, x0, y0, w, h, offline ? '#080B0C' : '#0A1414')
    rect(g, x0, y0, w, 13, offline ? '#0E2224' : '#0F3438')
    this.texts.push({ t: 'CLEARED // PULL REQUESTS', x: x0 + 5, y: y0 + 10, size: 12, color: '#BFF6F8' })
    this.prs.forEach((card, i) => {
      const st = card.state, slam = this.slam(card.key)
      const cx = x0 + 5 - slam * 8, cy = y0 + 17 + i * 31 - slam * 3, cw = w - 10 + slam * 16, ch = 27 + slam * 6
      const fill = st === 'tests' ? '#0E2A2C' : st === 'ready' ? '#3A2C0E' : '#1A1D22', acc = st === 'tests' ? '#5CE1E6' : st === 'ready' ? '#FFD27A' : '#6B7480'
      if (st === 'ready') rect(g, cx - 1, cy - 1, cw + 2, ch + 2, Math.floor(T * 3) % 2 ? '#FFD27A' : '#B8862E')
      rect(g, cx, cy, cw, ch, fill); rect(g, cx, cy, 3, ch, acc); rect(g, cx + cw - 7, cy + 4, 3, 3, acc)
      const col = st === 'tests' ? '#BFF6F8' : st === 'ready' ? '#FFE3A8' : '#9AA3AE'
      this.texts.push({ t: `${card.id} ${card.tag}`.slice(0, 22), x: cx + 7, y: cy + 11, size: 12, color: col })
      this.texts.push({ t: st === 'tests' ? 'TESTS PASSING' : st === 'ready' ? 'READY TO REVIEW' : 'MERGED', x: cx + 7, y: cy + 22, size: 11, color: col })
      if (st === 'ready' || st === 'merged') {
        const rs = this.t - this.readyAt, sl = st === 'ready' && rs < 0.25 ? 1 + (1 - rs / 0.25) * 1.4 : 1
        this.texts.push({ t: st === 'ready' ? 'REVIEW' : 'MERGED', x: cx + cw - 30, y: cy + 17, size: 12 * sl, color: st === 'ready' ? '#FF4D5E' : '#5E6670', rot: -0.22, box: true, align: 'center' })
      }
    })
    if (!this.prs.length) this.texts.push({ t: 'NOTHING CLEARED YET', x: x0 + w / 2, y: y0 + 64, size: 11, color: '#3A6A6E', align: 'center' })
    if (!offline) this.glows.push([x0 + w / 2, y0 + h / 2, 90, 0.12, '92,225,230'])
  } // prettier-ignore

  private drawGlobe(g: Ctx, T: number, alarm: boolean, offline: boolean, act: Record<string, boolean>) {
    const cx = 360, cy = 94, r = 44, busy = Object.keys(act).length > 0
    rect(g, 264, 36, 192, 118, '#0A0706'); rect(g, 266, 38, 188, 114, offline ? '#05060A' : '#100905')
    const base = offline ? '90,130,200' : alarm ? '255,80,90' : '255,170,80'
    for (let i = 0; i < 72; i++) {
      const an = (i / 72) * Math.PI * 2 + T * (offline ? 0.05 : 0.25)
      if (i % 3 !== 2) { g.fillStyle = `rgba(${base},0.55)`; g.fillRect(Math.round(cx + Math.cos(an) * (r + 9)), Math.round(cy + Math.sin(an) * (r + 9)), 1, 1) }
      const an2 = (-i / 72) * Math.PI * 2 + T * (offline ? 0.04 : 0.4)
      if (i % 6 < 4) { g.fillStyle = `rgba(${base},0.35)`; g.fillRect(Math.round(cx + Math.cos(an2) * (r + 15)), Math.round(cy + Math.sin(an2) * (r + 15) * 0.98), 1, 1) }
    }
    const rot = T * (offline ? 0.08 : busy ? 0.45 : 0.25)
    const land = (la: number, lo: number) => Math.sin(la * 0.09 + 1.3) * Math.cos(lo * 2.1) + Math.sin(lo * 3.3 + la * 0.05) * 0.6 + Math.cos(la * 0.17 - lo * 1.2) * 0.5 > 0.45
    for (let la = -78; la <= 78; la += 6) {
      const a1 = (la * Math.PI) / 180, cl = Math.cos(a1), ring = Math.max(6, Math.round(64 * cl))
      for (let j = 0; j < ring; j++) {
        const lo = (j / ring) * Math.PI * 2, a2 = lo + rot, z = cl * Math.cos(a2)
        if (z < -0.05) continue
        const isLand = land(la, lo), px = cx + r * cl * Math.sin(a2), py = cy - r * Math.sin(a1) * 0.98
        if (!isLand && (j + la) % 3) continue
        g.fillStyle = `rgba(${base},${((0.15 + 0.85 * z) * (isLand ? 1 : 0.35)).toFixed(3)})`
        g.fillRect(Math.round(px), Math.round(py), isLand && z > 0.5 ? 2 : 1, 1)
      }
    }
    // the radar sweep during deep scans
    if (this.mode === 'deep') {
      const sw = T * 1.4
      for (let j = 0; j < 14; j++) { g.beginPath(); g.moveTo(cx, cy); g.arc(cx, cy, r + 4, sw - j * 0.06, sw - j * 0.06 + 0.07); g.closePath(); g.fillStyle = `rgba(${base},${(0.18 * (1 - j / 14)).toFixed(3)})`; g.fill() }
    }
    for (let k = 0; k < 3; k++) {
      const an = T * (0.8 + k * 0.3) + k * 2.1, px = cx + Math.cos(an) * (r + 20 + k * 3), py = cy + Math.sin(an) * (r * 0.35 + k * 4) - k * 6
      g.fillStyle = k === 0 ? '#5CE1E6' : '#FFD27A'; g.fillRect(Math.round(px), Math.round(py), 2, 2)
    }
    this.texts.push({ t: offline ? 'AUDIT CORE / STANDBY' : 'AUDIT CORE', x: cx, y: 150, size: 11, color: offline ? '#4A6A9A' : alarm ? '#FF7A84' : '#FFD27A', align: 'center' })
    this.glows.push([cx, cy, 80, offline ? 0.12 : 0.22, base])
  } // prettier-ignore

  private drawDesk(g: Ctx, d: (typeof DESKS)[number], act: Record<string, boolean>, offline: boolean, T: number) {
    const s = sc(d.yF), yB = d.yF - 8 * s, fh = 12 * s
    const xLF = X(d.u0, d.yF), xRF = X(d.u1, d.yF), xLB = X(d.u0, yB), xRB = X(d.u1, yB)
    poly(g, [[xLB, yB], [xRB, yB], [xRF, d.yF], [xLF, d.yF]], '#3A2A1E')
    poly(g, [[xLB, yB], [xRB, yB], [xRB, yB + 1], [xLB, yB + 1]], '#4A3424')
    d.st.forEach((st, si) => {
      const on = !!act[st[0]], kinds = st[3], n = kinds.length
      kinds.forEach((kd, i) => {
        const ua = st[1] + ((i + 0.07) * (st[2] - st[1])) / n, ub = st[1] + ((i + 0.93) * (st[2] - st[1])) / n
        const x0 = X(ua, yB), x1 = X(ub, yB), mh = 15 * s, my = yB - mh - 2.4 * s
        rect(g, (x0 + x1) / 2 - s, yB - 2.6 * s, 2 * s, 2.6 * s, '#14100C')
        this.mon(g, x0, my, x1 - x0, mh, kd, on, T, offline, i * 7 + si * 3 + Math.round(d.yF))
        if (!offline) this.glows.push([(x0 + x1) / 2, my + mh / 2, (x1 - x0) * 0.9, on ? 0.2 : 0.06, '255,155,61'])
      })
      const um = (st[1] + st[2]) / 2, yk = d.yF - 3.4 * s, kx0 = X(um - 0.06, yk), kx1 = X(um + 0.06, yk)
      rect(g, kx0, yk - s, kx1 - kx0, 1.6 * s, '#1A120C')
      if (on) rect(g, kx0 + 1 + (Math.floor(T * 12) % 4) * 2, yk - s, 2, 1, '#FF9B3D')
      if ((si + d.yF) % 2 === 0) {
        const mx = X(st[2] - 0.05, yk), my2 = yk - 2.4 * s
        rect(g, mx, my2, 2.2 * s, 2.6 * s, '#E8E2D6'); rect(g, mx + 2.2 * s, my2 + 0.6 * s, 0.8 * s, 1.2 * s, '#E8E2D6')
        if (!offline && Math.random() < 0.03) this.parts.push({ x: mx + s, y: my2 - 1, vx: (Math.random() - 0.5) * 4, vy: -8, g: -2, life: 1.2, c: 'rgba(255,240,220,0.35)', s: 1, floor: 999 })
      }
      if (st[0] === 'slides' || st[0] === 'plans') { const px = X(st[1] + 0.03, yk); rect(g, px, yk - 1.6 * s, 4 * s, 1.2 * s, '#D9B26A'); rect(g, px + s, yk - 1.6 * s, 1.4 * s, 0.6 * s, '#FF4D5E') }
      this.texts.push({ t: LABEL[st[0]], x: X(um, d.yF), y: d.yF + 8 * s, size: 11, color: offline ? '#3A3A44' : on ? '#FFD27A' : '#8A6A50', align: 'center' })
    })
    rect(g, xLF, d.yF, xRF - xLF, fh, '#1E150F')
    rect(g, xLF, d.yF, xRF - xLF, 1, offline ? '#3A2414' : '#FF9B3D')
    rect(g, xLF, d.yF + fh - 2 * s, xRF - xLF, 2 * s, '#120C08')
    const n = Math.max(3, Math.floor((xRF - xLF) / 14))
    for (let i = 0; i < n; i++) { const lx = xLF + 6 + i * ((xRF - xLF - 12) / n); rect(g, lx, d.yF + 3 * s, 1.4 * s, 0.9 * s, Math.floor(T * 2 + i * 0.7 + d.yF) % 5 === 0 ? (offline ? '#3A1A1E' : '#5BD68A') : '#2A1E16') }
  } // prettier-ignore

  private drawBench(g: Ctx, T: number, offline: boolean) {
    const u0 = 0.865, y0 = 222, y1 = 262, s0 = sc(y0), s1 = sc(y1), h0 = 13 * s0, h1 = 13 * s1
    const a = [X(u0, y0), y0], b = [X(u0, y1), y1], c = [X(1.0, y1), y1], d = [X(1.0, y0), y0]
    poly(g, [[a[0], a[1] - h0], [d[0], d[1] - h0], [c[0], c[1] - h1], [b[0], b[1] - h1]], '#5A4636')
    poly(g, [[a[0], a[1] - h0], [b[0], b[1] - h1], [b[0], b[1]], [a[0], a[1]]], '#2E2218')
    rect(g, b[0], b[1] - h1, c[0] - b[0], h1, '#3A2A1E')
    poly(g, [[a[0], a[1] - h0], [b[0], b[1] - h1], [b[0], b[1] - h1 + 1], [a[0], a[1] - h0 + 1]], offline ? '#3A2414' : '#FF9B3D')
    const vx = X(0.9, 232), vy = 232 - 13 * sc(232)
    rect(g, vx, vy - 4, 8, 4, '#6B7480'); rect(g, vx + 2, vy - 6, 4, 2, '#9AA3B5')
    const tx = X(0.93, 255), ty = 255 - 13 * sc(255)
    rect(g, tx, ty - 5, 12, 5, '#B8303C'); rect(g, tx + 4, ty - 7, 4, 2, '#8A1E28')
    rect(g, X(0.96, 228), 160, 1, 228 - 13 * sc(228) - 160, '#3A3F4C')
    rect(g, X(0.96, 228) - 5, 158, 8, 3, '#4A4F5E'); if (!offline) this.glows.push([X(0.96, 228) - 2, 175, 30, 0.2, '255,210,150'])
    for (const ag of this.agents) {
      if (ag.at !== 'bench') continue
      const yy = ag.y, ss = sc(yy), xx = X(0.89, yy), top = yy - 13 * ss
      rect(g, xx, top - 1.5 * ss, 6 * ss, 1.5 * ss, Math.floor(T * 4) % 2 ? '#FFD27A' : '#D9B26A')
      this.glows.push([xx + 3 * ss, top, 26, 0.35 + 0.15 * Math.sin(T * 14), '255,190,90'])
    }
  } // prettier-ignore

  private drawTest(g: Ctx, T: number, offline: boolean, act: Record<string, boolean>) {
    const ybase = 252, xa = X(-0.985, ybase), xb = X(-0.875, ybase), w = xb - xa, on = !!act.test
    rect(g, xa - 3, ybase - 6, w + 6, 6, '#2A2E38'); rect(g, xa - 3, ybase - 6, w + 6, 1, '#4A4F5E')
    g.globalCompositeOperation = 'lighter'
    rect(g, xa, 150, w, ybase - 156, on ? 'rgba(92,225,230,0.12)' : 'rgba(92,225,230,0.05)')
    rect(g, xa, 150, 1, ybase - 156, 'rgba(92,225,230,0.55)'); rect(g, xb - 1, 150, 1, ybase - 156, 'rgba(92,225,230,0.55)')
    rect(g, xa + 3, 152, 2, ybase - 160, 'rgba(255,255,255,0.10)')
    if (on) {
      const sy = 156 + ((T * 50) % (ybase - 166))
      rect(g, xa, sy, w, 2, '#5CE1E6')
      const fy = 190 + Math.sin(T * 3) * 4; rect(g, xa + w / 2 - 6, fy, 12, 9, '#0E2A2C'); rect(g, xa + w / 2 - 5, fy + 1, 10, 7, Math.floor(T * 4) % 2 ? '#5CE1E6' : '#2A8A8E')
    }
    // a green flash when a fix passes its tests
    const pass = this.t - this.readyAt
    if (pass < 0.6) rect(g, xa, 150, w, ybase - 156, `rgba(111,217,138,${(0.5 * (1 - pass / 0.6)).toFixed(3)})`)
    g.globalCompositeOperation = 'source-over'
    rect(g, xa - 3, 145, w + 6, 6, '#3A3F4C'); rect(g, xa - 3, 150, w + 6, 1, '#5CE1E6')
    this.texts.push({ t: 'TEST BAY', x: xa + w / 2, y: 140, size: 11, color: on ? '#BFF6F8' : offline ? '#3A4A5A' : '#6A9A9E', align: 'center', glow: on })
    this.glows.push([xa + w / 2, 200, 50, on ? 0.3 : 0.08, '92,225,230'])
  } // prettier-ignore

  private poseOf(a: Agent): [string, Face] {
    const poked = this.t - a.poke < 1.4
    if (a.walking) return ['walk', a.face]
    if (a.seated) {
      if (a.anim === 'sleep' && !poked)
        return [a.front ? 'sleepFront' : 'sleepSit', a.front ? 'front' : 'back']
      if (a.anim === 'sleep' && poked)
        return [a.front ? 'sitFront' : 'sit', a.front ? 'front' : 'back']
      if (a.anim === 'stretch') return ['sitStretch', 'back']
      if (a.anim === 'cheer') return ['cheer', 'front']
      return ['sit', 'back']
    }
    if (a.anim === 'cheer') return ['cheer', 'front']
    if (a.anim === 'hammer') return ['hammer', 'right']
    if (a.anim === 'scan') return ['scan', 'left']
    if (a.anim === 'pin') return ['pin', 'back']
    if (a.anim === 'stretch') return ['stretch', 'front']
    return ['idle', a.face]
  }

  private drawAgent(g: Ctx, a: Agent, T: number) {
    const s = sc(a.y), x = X(a.u, a.y), [pose, view] = this.poseOf(a)
    this.fig(g, a.id, Math.round(x), Math.round(a.y), s, view, pose, T, { off: a.off, carry: a.carry })
    const top = a.y + (/^sit|^sleep/.test(pose) ? -24 : -33) * s
    const poked = this.t - a.poke < 1.4
    this.post.push((gg) => {
      if (pose === 'sleepSit' || pose === 'sleepFront') {
        for (let i = 0; i < 3; i++) {
          const ph = (T * 0.45 + i / 3 + a.off) % 1, zx = x + 5 * s + ph * 10 * s, zy = top - ph * 16, z = Math.max(3, Math.round(2.4 * s))
          gg.fillStyle = `rgba(159,190,232,${(1 - ph).toFixed(2)})`
          gg.fillRect(Math.round(zx), Math.round(zy), z, 1); gg.fillRect(Math.round(zx + z - 2), Math.round(zy + 1), 1, 1); gg.fillRect(Math.round(zx + 1), Math.round(zy + 2), 1, 1); gg.fillRect(Math.round(zx), Math.round(zy + 3), z, 1)
        }
      }
      if (pose === 'hammer' && Math.floor(T * 3) % 2) { gg.fillStyle = '#9FE8F0'; gg.fillRect(Math.round(x - 4 * s), Math.round(top + 2 * s), 1, 2) }
      const em = a.emote && this.t < a.emote.until ? a.emote.e : poked ? '?' : null
      if (em) {
        const ex = Math.round(x), ey = Math.round(top - 6 - (a.emote && this.t - a.emote.from < 0.12 ? 2 : 0))
        const P = (dx: number, dy: number, w: number, h: number, c: string) => { gg.fillStyle = c; gg.fillRect(ex + dx, ey + dy, w, h) }
        P(-5, -11, 11, 11, '#FFFFFF'); P(-1, 0, 3, 2, '#FFFFFF'); P(-5, -11, 11, 1, '#E8E2D6')
        if (em === '!') { P(0, -9, 1, 5, '#FF4D5E'); P(0, -3, 1, 1, '#FF4D5E') }
        if (em === '?') { P(-1, -9, 3, 1, '#2B3A66'); P(1, -8, 1, 2, '#2B3A66'); P(0, -6, 1, 1, '#2B3A66'); P(0, -3, 1, 1, '#2B3A66') }
        if (em === 'ok') { P(-2, -6, 5, 1, '#E8A51A'); P(0, -8, 1, 5, '#E8A51A'); P(2, -10, 1, 1, '#E8A51A') }
        if (em === 'heart') { P(-3, -9, 2, 1, '#FF5F8F'); P(1, -9, 2, 1, '#FF5F8F'); P(-4, -8, 8, 2, '#FF5F8F'); P(-3, -6, 6, 1, '#FF5F8F'); P(-2, -5, 4, 1, '#FF5F8F'); P(-1, -4, 2, 1, '#FF5F8F') }
      }
    })
  } // prettier-ignore

  private drawTexts(ctx: Ctx, k: number, T: number, ox: number, oy: number) {
    for (const t of this.texts) {
      ctx.save()
      if (t.clip) { ctx.beginPath(); ctx.rect(t.clip[0] * k + ox, t.clip[1] * k + oy, t.clip[2] * k, t.clip[3] * k); ctx.clip() }
      ctx.translate(t.x * k + ox, t.y * k + oy)
      if (t.rot) ctx.rotate(t.rot)
      const fs = Math.round((t.size * k) / 2)
      ctx.font = `${fs}px Silkscreen, monospace`
      ctx.textAlign = t.align || 'left'
      if (t.box) { const w = ctx.measureText(t.t).width + 10; ctx.strokeStyle = t.color; ctx.lineWidth = 2; ctx.strokeRect(-w / 2, -fs, w, fs + 6) }
      if (t.glow) { ctx.shadowColor = t.color; ctx.shadowBlur = 10 }
      ctx.fillStyle = t.color
      ctx.fillText(t.t, 0, 0)
      ctx.restore()
    }
    const fs = Math.round((13 * k) / 2)
    ctx.font = `${fs}px Silkscreen, monospace`
    ctx.textAlign = 'center'
    for (const a of this.agents) {
      if (!a.say) continue
      const s = sc(a.y), sx = X(a.u, a.y) * k + ox, sy = (a.y + (a.seated ? -27 : -37) * s) * k + oy - 22
      const txt = /ING$/.test(a.say) ? a.say + '.'.repeat(1 + (Math.floor(T * 2.5) % 3)) : a.say
      const w = Math.ceil(ctx.measureText(a.say + '...').width) + 22, pk = Math.min(1, (this.t - a.sayAt) / 0.15), scl = 0.7 + 0.3 * pk + (pk < 1 ? 0.08 : 0)
      const hot = /PINNING/.test(a.say), ok = /APPROVAL|COMPLETE/.test(a.say), W = 720 * k
      ctx.save(); ctx.translate(Math.max(w / 2 + 6, Math.min(W - w / 2 - 6, sx)), sy); ctx.scale(scl, scl)
      ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.fillRect(-w / 2 + 3, -fs - 4, w, fs + 14)
      ctx.fillStyle = hot ? '#FF4D5E' : ok ? '#FFD27A' : '#F7EBDD'; ctx.fillRect(-w / 2, -fs - 7, w, fs + 14)
      ctx.beginPath(); ctx.moveTo(-6, 7); ctx.lineTo(6, 7); ctx.lineTo(0, 14); ctx.closePath(); ctx.fill()
      ctx.fillStyle = hot ? '#FFFFFF' : '#1A0E06'; ctx.fillText(txt, 0, 1); ctx.restore()
    }
    const hv = this.agents.find((a) => a.id === this.hover)
    if (hv) {
      const C = CREW[hv.id], s = sc(hv.y), ax = X(hv.u, hv.y) * k + ox, ay = hv.y * k + oy
      const bw = 320, bh = 150, bx = Math.max(8, Math.min(720 * k - bw - 8, ax + 30)), by = Math.max(70, Math.min(405 * k - bh - 70, ay - bh - 20 * s))
      ctx.fillStyle = 'rgba(8,5,3,0.94)'; ctx.fillRect(bx, by, bw, bh); ctx.strokeStyle = C.tie; ctx.lineWidth = 2; ctx.strokeRect(bx + 1, by + 1, bw - 2, bh - 2)
      ctx.fillStyle = '#1A120C'; ctx.fillRect(bx + 10, by + 10, 96, bh - 20)
      ctx.fillStyle = 'rgba(255,155,61,0.12)'; for (let i = 0; i < 6; i++) ctx.fillRect(bx + 10, by + 14 + i * 22, 96, 1)
      this.fig(ctx, hv.id, bx + 58, by + bh - 14, 3.6, 'front', 'idle', T, { off: hv.off })
      const st = hv.anim === 'sleep' ? 'ASLEEP AT STATION' : hv.say ? hv.say : hv.walking ? 'ON THE MOVE' : 'STANDING BY'
      ctx.textAlign = 'left'; ctx.font = '16px Silkscreen, monospace'; ctx.fillStyle = C.tie; ctx.fillText(C.name, bx + 120, by + 32)
      ctx.font = '12px Silkscreen, monospace'; ctx.fillStyle = '#F7EBDD'; ctx.fillText(C.role, bx + 120, by + 54)
      ctx.fillStyle = '#BFA58F'; ctx.fillText(`${C.code} / CLEARANCE OMEGA`, bx + 120, by + 74)
      ctx.fillStyle = '#FFD27A'; ctx.fillText(st, bx + 120, by + 100)
      ctx.strokeStyle = '#FF4D5E'; ctx.lineWidth = 2; ctx.save(); ctx.translate(bx + 250, by + 128); ctx.rotate(-0.15); ctx.strokeRect(-48, -14, 96, 22); ctx.fillStyle = '#FF4D5E'; ctx.textAlign = 'center'; ctx.fillText('TOP SECRET', 0, 2); ctx.restore()
    } else if (this.hoverCard && this.hoverCard.kind !== 'agent') {
      // hovering a pinned card shows the issue or pull request
      const card = this.hoverCard.card, issue = this.hoverCard.kind === 'issue'
      const bw = 360, bh = 64, bx = (issue ? 110 : 248) * k + ox, by = 156 * k + oy
      ctx.fillStyle = 'rgba(8,5,3,0.94)'; ctx.fillRect(bx, by, bw, bh); ctx.strokeStyle = issue ? '#FF4D5E' : '#5CE1E6'; ctx.lineWidth = 2; ctx.strokeRect(bx + 1, by + 1, bw - 2, bh - 2)
      ctx.textAlign = 'left'; ctx.font = '12px Silkscreen, monospace'; ctx.fillStyle = issue ? '#FFD0D4' : '#BFF6F8'; ctx.fillText(card.id, bx + 12, by + 22)
      ctx.font = '13px "IBM Plex Sans", sans-serif'; ctx.fillStyle = '#F7EBDD'; ctx.fillText(card.title.slice(0, 52), bx + 12, by + 44)
    }
  } // prettier-ignore

  frame(now: number, still: boolean, dt: number) {
    this.step(still ? 0 : dt)
    this.draw(still ? 0 : now / 1000)
  }

  private draw(T: number) {
    const g = this.buf.getContext('2d')
    const ctx = this.view.getContext('2d')
    if (!g || !ctx) return
    g.setTransform(1, 0, 0, 1, 0, 0); g.imageSmoothingEnabled = false; g.globalCompositeOperation = 'source-over'
    this.texts = []; this.post = []; this.glows = []
    const offline = this.mode === 'offline', alarm = !offline && this.alarm
    const act: Record<string, boolean> = {}
    for (const a of this.agents) if (a.at) act[a.at] = true
    g.fillStyle = '#050302'; g.fillRect(0, 0, 720, 405)
    this.drawRoom(g, T, offline, alarm, act)
    const list: { k: number; d: () => void }[] = []
    for (const d of DESKS) list.push({ k: d.yF, d: () => this.drawDesk(g, d, act, offline, T) })
    for (const c of CHAIRS) {
      if (this.agents.some((a) => a.loc === c[0] && a.seated && a.front && !a.walking)) continue
      list.push({ k: c[2] + 0.6, d: () => this.chair(g, X(c[1], c[2]), c[2], sc(c[2]), c[0] === 'seat_lead') })
    }
    for (const a of this.agents) list.push({ k: a.y + (a.seated ? 0 : 0.3), d: () => this.drawAgent(g, a, T) })
    list.push({ k: 262.5, d: () => this.drawBench(g, T, offline) })
    list.push({ k: 252.5, d: () => this.drawTest(g, T, offline, act) })
    list.sort((p, q) => p.k - q.k).forEach((o) => o.d())
    rect(g, 0, 393, 720, 12, '#0A0605'); rect(g, 0, 393, 720, 1, offline ? '#3A2414' : '#FF9B3D')
    for (let i = 0; i < 18; i++) rect(g, 18 + i * 40, 398, 3, 2, Math.floor(T * 3 + i) % 6 === 0 ? '#FFD27A' : '#3A2414')
    g.globalCompositeOperation = 'lighter'
    for (const b of this.beams) {
      const p = (this.t - b.t0) / 1.2, al = (1 - p) * 0.8
      g.strokeStyle = `rgba(${b.c},${al.toFixed(3)})`; g.lineWidth = 2; g.beginPath(); g.moveTo(b.x0, b.y0); g.lineTo(b.x1, b.y1); g.stroke()
      const q = Math.min(1, p * 2.5); g.fillStyle = `rgba(255,255,255,${al.toFixed(3)})`; g.fillRect(Math.round(b.x0 + (b.x1 - b.x0) * q) - 1, Math.round(b.y0 + (b.y1 - b.y0) * q) - 1, 3, 3)
    }
    if (act.holo) { g.strokeStyle = `rgba(255,190,90,${(0.25 + 0.15 * Math.sin(T * 6)).toFixed(3)})`; g.lineWidth = 1; g.beginPath(); g.moveTo(360, 330); g.lineTo(360, 140); g.stroke() }
    if (alarm) {
      ;[120, 242].forEach((bx, i) => {
        const an = T * 4.2 + i * Math.PI
        g.fillStyle = 'rgba(255,50,60,0.10)'; g.beginPath(); g.moveTo(bx, 32); g.lineTo(bx + Math.cos(an - 0.2) * 700, 32 + Math.abs(Math.sin(an - 0.2)) * 520); g.lineTo(bx + Math.cos(an + 0.2) * 700, 32 + Math.abs(Math.sin(an + 0.2)) * 520); g.closePath(); g.fill()
      })
    }
    g.globalCompositeOperation = 'source-over'
    for (const p of this.parts) { g.fillStyle = p.c; g.fillRect(Math.round(p.x), Math.round(p.y), p.s, p.s) }
    if (offline) { g.fillStyle = 'rgba(4,8,24,0.58)'; g.fillRect(0, 0, 720, 405) }
    if (alarm) { const since = this.t - this.alarmAt, fl = since < 1.4 ? 0.2 * (1 - since / 1.4) : 0; g.fillStyle = `rgba(255,30,40,${(0.04 + 0.04 * (0.5 + 0.5 * Math.sin(T * 6)) + fl).toFixed(3)})`; g.fillRect(0, 0, 720, 405) }
    if (this.t - this.readyAt < 0.5) { g.fillStyle = `rgba(255,210,122,${(0.25 * (1 - (this.t - this.readyAt) / 0.5)).toFixed(3)})`; g.fillRect(0, 0, 720, 405) }
    g.globalCompositeOperation = 'lighter'
    for (const gl of this.glows) { const rg = g.createRadialGradient(gl[0], gl[1], 0, gl[0], gl[1], gl[2]); rg.addColorStop(0, `rgba(${gl[4]},${gl[3]})`); rg.addColorStop(1, `rgba(${gl[4]},0)`); g.fillStyle = rg; g.fillRect(gl[0] - gl[2], gl[1] - gl[2], gl[2] * 2, gl[2] * 2) }
    g.globalCompositeOperation = 'source-over'
    for (const fn of this.post) fn(g)
    const vg = g.createRadialGradient(360, 200, 180, 360, 200, 470); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.55)'); g.fillStyle = vg; g.fillRect(0, 0, 720, 405)
    const c = this.view, cw = c.clientWidth || 1440, ch = Math.round((cw * 9) / 16), dpr = Math.min(window.devicePixelRatio || 1, 2)
    if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) { c.width = Math.round(cw * dpr); c.height = Math.round(ch * dpr) }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.imageSmoothingEnabled = false
    const k = cw / 720, sh = this.shake > 0 ? 3 + this.shake * 8 : 0, ox = sh ? Math.round((Math.random() - 0.5) * sh) : 0, oy = sh ? Math.round((Math.random() - 0.5) * sh) : 0
    ctx.fillStyle = '#050302'; ctx.fillRect(0, 0, cw, ch)
    ctx.drawImage(this.buf, 0, 0, 720, 405, ox, oy, cw, ch)
    this.drawTexts(ctx, k, T, ox, oy)
    ctx.fillStyle = 'rgba(0,0,0,0.07)'; for (let yy = 0; yy < ch; yy += 3) ctx.fillRect(0, yy, cw, 1)
  } // prettier-ignore

  // ---- pointer: agents show dossiers, cards show their issue or pull request

  private pick(clientX: number, clientY: number): Picked | null {
    const r = this.view.getBoundingClientRect()
    const bx = (clientX - r.left) * (720 / r.width)
    const by = (clientY - r.top) * (405 / r.height)
    let best: Agent | null = null
    let bd = 1e9
    for (const a of this.agents) {
      const s = sc(a.y),
        x = X(a.u, a.y),
        d = Math.abs(bx - x),
        top = a.y - (a.seated ? 24 : 33) * s
      if (d < 8 * s && by > top && by < a.y + 2 && d < bd) {
        bd = d
        best = a
      }
    }
    if (best) return { kind: 'agent', name: best.id }
    const row = Math.floor((by - 57) / 31)
    if (row >= 0 && row < 3 && by - 57 - row * 31 < 27) {
      if (bx >= 115 && bx <= 247 && this.issues[row])
        return { kind: 'issue', card: this.issues[row] }
      if (bx >= 473 && bx <= 605 && this.prs[row]) return { kind: 'pr', card: this.prs[row] }
    }
    return null
  }

  move(clientX: number, clientY: number) {
    const p = this.pick(clientX, clientY)
    this.hover = p?.kind === 'agent' ? p.name : null
    this.hoverCard = p
  }

  leave() {
    this.hover = null
    this.hoverCard = null
  }

  /** Clicking an agent pokes it; clicking a card returns it so the page can show details. */
  click(clientX: number, clientY: number): Picked | null {
    const p = this.pick(clientX, clientY)
    if (p?.kind === 'agent') {
      const a = this.agents.find((x) => x.id === p.name)
      if (a?.anim === 'sleep') a.poke = this.t
      else if (a) a.emote = { e: 'heart', from: this.t, until: this.t + 1.2 }
    }
    return p
  }
}

export const DOSSIERS = Object.fromEntries(
  (Object.keys(CREW) as AgentId[]).map((id) => [
    id,
    `${CREW[id].name}, ${CREW[id].code}, ${CREW[id].role.toLowerCase()}`,
  ]),
)
