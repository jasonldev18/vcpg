# Design

The look is **Solar**: a warm, dark JARVIS-style command interface in amber, red and gold, with cyan reserved for *you* (whenever it is the user's turn). Agents are small retro pixel characters. Motion is constant but quiet.

Visual reference for every screen is in `design/prototypes/`. They were built in a design canvas whose runtime (`support.js`) is not included, so read them as source: copy layout, CSS values and the canvas drawing code, and port the drawing code into React canvas components. Only the Solar theme and the blob core ship; `MissionControl.dc.html` still contains the other theme and core options, which should be ignored.

## 1. Tokens

```css
:root {
  --bg:    #0D0A08;               /* page */
  --panel: rgba(30, 20, 14, .78); /* glass panels */
  --acc:   #FF9B3D;               /* amber: primary accent, active links */
  --acc2:  #FF4D5E;               /* red: alerts, gradients, siren */
  --acc3:  #FFD27A;               /* gold: highlights, ripple peaks */
  --you:   #5CE1E6;               /* cyan: the user's turn, user input */
  --text:  #F7EBDD;
  --mute:  #BFA58F;
  --dim:   #6B4A30;               /* idle links and inactive lines */
}
```

- **Panels:** `--panel` background with an amber 8% top-left tint, 1px amber border at 26% opacity, a soft red drop shadow, and a top sheen: a 2px gradient bar (acc → acc2 → acc3) across 60% of the top edge, animated across in 5s.
- **Brand text:** gradient fill acc → acc2 → acc3.
- **Status colours:** pass `#6FD98A`, partial `--acc3`, missing/fail `--acc2`. Never colour alone: pair with an icon or word.

## 2. Type

| Use | Font |
|---|---|
| Display, headings, labels (uppercase, letter-spacing .08em) | Oxanium 500 to 700 |
| Body | IBM Plex Sans 400/500 |
| Code, console, numbers, metadata | IBM Plex Mono 400/500 |
| Pixel labels in the audit bay and slide stamps | Silkscreen |

Load from Google Fonts or self-host. Body size 15px, line height 1.55. Minimum text size 12px.

## 3. Motion

All motion respects `prefers-reduced-motion`: the background goes still, links stop flowing, the blob holds a static shape, and transitions become fades.

### 3.1 Background: motes with cursor ripple

- A staggered grid of small dots (22px spacing, alternate rows offset 11px), radius 1px, amber at 10% opacity.
- Moving the cursor more than 46px drops a ripple point (keep the last 9). Each ripple expands to 280px over 1.7s. A dot near the ring is pushed outward by up to 3.5px, grows by up to 0.9px and brightens toward gold. Strength falls off with a gaussian (`exp(-(d - r)^2 / 1100)`) and with age.
- The effect is subtle: no lines, no large shapes. Code reference: `drawBg` in `MissionControl.dc.html`.

### 3.2 3D tilt

Panels tilt toward the cursor using `--rx` / `--ry` (−1..1 from cursor position): at most 3° rotation with `perspective(1200px)`, eased with a 250ms transition. A radial highlight follows the cursor (`--mx`, `--my`).

### 3.3 Orchestrator core (blob) and agent links

- The core sits in the centre of the mission control stage: a radial glow (white centre → hot colour → red fade, radius 88px) pulsing on a 600ms sine.
- Four nested wobbling rings (base radius 38 + 11 per layer; radius modulated by `6·sin(3a + t/700 + l) + 4·sin(5a − t/520 + 2l)`), stroked in hot, red, gold, hot with decreasing opacity, plus 9 orbiting 3px motes.
- *Hot* is amber normally and cyan when it is the user's turn.
- Each agent connects to the core with a curved link (quadratic, alternate sides bend ±22px). Idle: dashed `--dim` line with one slow 3px mote drifting along it. Active: dashed amber (cyan on the user's turn) with flowing dash offset, glow, three comet trails of 10 fading squares, and two expanding rings around the agent.
- Code reference: `drawStage` in `MissionControl.dc.html`.
- **Clicking the core** opens Core access: the core scales up to fill a centred overlay (Motion spring, ~400ms) and the key panels fade in around it.

### 3.4 Transitions

Motion (`motion/react`) for panel enter and exit (fade + 8px rise, 220ms), list reorders, and the step hand-off (the finished step's chip flies to the deck counter). Keep durations between 150 and 450ms.

## 4. Pixel agents

### 4.1 Build crew (mission control)

12×12 pixel sprites drawn at 5px per pixel, from the character maps in `MissionControl.dc.html` (`AGENTS`). Palette keys: `o` outline `#2E3A63`, `w` eye white, `p` pupil `#10162B`, `k` blush `#FF8FA3`, `m` dark `#141A30`, `y` gold `#FFD45E`, `b`/`s`/`h` body, shade and highlight per agent.

| Agent | Body | Detail |
|---|---|---|
| Planner | blue `#5AA9FF` | antenna |
| Tutor | green `#6FD98A` | graduation cap with tassel |
| Builder | orange `#FF9A52` | hard hat |
| Interviewer | pink `#FF7EB6` | headset |
| Reviewer | violet `#B58CFF` | ears and magnifier tail |
| Grader | teal `#41D6C3` | visor |
| Slide writer | gold `#FFD45E` | monitor head |

Agents idle-bob (2px, 2.4s, staggered), blink every few seconds, and show a status word under their name while working (*asking*, *scoring*, *drafting*, ...).

### 4.2 Audit crew (audit bay)

Front-facing, full-body pixel agents in **black suits, white shirts, coloured ties and sunglasses**: a secret-mission team. Each has a code name badge.

| Agent | Code | Role | Tie | Look |
|---|---|---|---|---|
| Rook | AGENT 001 | Audit lead | red `#FF4D5E` | silver hair, long coat |
| Bolt | AGENT 004 | Build auditor | blue `#5AA9FF` | dark hair |
| Echo | AGENT 007 | Teaching auditor | teal `#41D6C3` | dark hair, earpiece mic |
| Pixel | AGENT 009 | Output auditor | gold `#FFD45E` | blond hair, pocket square |

Poses: sit and type, scan (handheld scanner with blinking cyan screen), carry, pin, stamp, cheer, stretch, walk. Exact pixel construction is in `Audit.dc.html` (`drawAgent`, `poseOf`).

## 5. Screens

| Screen | Prototype | Key parts |
|---|---|---|
| Mission control | `MissionControl.dc.html` | stage with core and 7 agents, step list, phase strip, current panel, live console, audit pill, Squad and Archive links |
| Core access | `MissionControl.dc.html` (click the core) | enlarged core, Anthropic key and GitHub token panels with test and status lights |
| Start a project | `Ideas.dc.html` | three path cards, topic input with chips, four idea cards with small visuals, expanded card with architecture diagram, steps and *What you will be asked* |
| Concept lesson | `Lesson.dc.html` | lesson rail (path), sections 01 to 06, interactive visual, code snippet, MC/TF/short/code questions, citation chips, *Community* block |
| Squad loadout | `Squad.dc.html` | grid of agent cards, model and effort selectors, relative profile bars, recommended/custom badges, reset and save |
| Audit bay | `Audit.dc.html` | full-screen pixel mission-control room (below) |
| Audit popups | `AuditPopups.dc.html` | the three pill states: offline, project scan, deep scan |
| Deck viewer | `Deck.dc.html` | slide strip, large slide, speaker notes, export menu (PowerPoint, PDF), version list |
| README coach | `Readme.dc.html` | editor, preview, coach notes tagged *does not match* / *gap* / *unclear*, readiness status |
| Archive | `Archive.dc.html` | project list, dossier view, mock interview setup (length, focus), interview chat with timer, live scorecard |

### 5.1 Audit bay

A full-screen, front-facing pixel room in a spaceship mission control, drawn on one canvas at 16:9 with `image-rendering: pixelated`:

- Rows of consoles facing a large front wall with screens; each auditor has a station (code, lessons, slides, lead).
- **Intel board** (left wall): red-lit, issues pinned as cards; a red siren light rotates when a high-severity issue lands, with a brief screen shake.
- **Repair bay** (side) where fixes are worked on, and a **glass test chamber** where they are tested (green flash on pass).
- **PR board** (right wall): cleared pull requests pinned and stamped *READY TO REVIEW* or *MERGED*.
- Central holo table labelled *AUDIT CORE*; a radar sweep during deep scans.
- Modes: *offline* (crew asleep at stations, dim lights), *project scan* (two or three agents active), *deep scan* (everyone moving, alarms, louder effects).
- Hovering an agent shows a dossier card (code name, role, current task); hovering a pinned card shows the issue or pull request. Clicking opens the detail in a side panel.
- Status text in Silkscreen: *COLLECTING REPORTS*, *CHECKING CODE*, *TRACING CAUSES*, *RUNNING TESTS*, *SCAN COMPLETE*.

## 6. Slides

16:9, Solar palette on a near-black background, Oxanium titles, IBM Plex Sans body. Prototypes: `SlideArchitecture.dc.html`, `SlideCoreLogic.dc.html`, `SlideEvaluation.dc.html`.

Layout: kicker (component label) and title at top; visual on the left two-thirds; decisions, failure and scale on the right; a footer strip with *questions I struggled with* and hint counts.

Visual kinds and their `spec`:

| Kind | Spec |
|---|---|
| `architecture` | `nodes: [{id, label, group}]`, `edges: [{from, to, label}]` |
| `flow` | `steps: [str]` (left to right with arrows) |
| `chart` | `type: bar|line|scatter`, `series: [{name, x: [], y: []}]`, `x_label`, `y_label` |
| `code` | `path`, `lines: [start, end]`, `highlight: [line]` (code is read from the commit, not written by the model) |
| `table` | `columns: [str]`, `rows: [[str]]` (max 5 rows) |

In the app the visuals are drawn live (SVG/canvas); exports render them to PNG (ARCHITECTURE section 10).

## 7. Idea card visuals

Each idea card has a small thumbnail that shows what using the project looks like. It is a fixed HTML/CSS template filled with content the idea generator writes (see `Ideas.dc.html`, the `.th` blocks):

| Template | Shows | Data |
|---|---|---|
| `chat` | a question bubble, an answer bubble, a cyan citation chip | `question`, `answer`, `cite` |
| `ranked` | a query chip over 3 labelled score bars | `query`, `items: [{label, score}]` |
| `cluster` | scattered dots with one dashed circle around a group and a label | `label`, `seed` |
| `code_hits` | grey code lines with two highlighted, a cyan `file : line` chip | `hit` |
| `chart` | 4 to 6 bars or a small line | `values`, `label` |
| `pipeline` | 3 to 5 chained blocks | `blocks` |

The expanded card shows the full architecture strip (4 to 6 chained blocks from `architecture`), concept chips marked *new* / *know the basics* / *used it before*, and *What you will be asked*. Difficulty labels: *Gentle*, *Medium*, *Stretch*.

## 8. Accessibility

- All text meets WCAG AA contrast on `--bg` (body text `--text`, secondary `--mute`).
- Every canvas has an `aria-label` describing what it shows, and every state shown on a canvas is also available as text (agent statuses, audit counts, gate progress).
- Full keyboard use: visible focus ring in `--you`, logical tab order, Escape closes overlays.
- `prefers-reduced-motion` honoured everywhere (section 3).
- Minimum viewport 1280px wide; desktop only.
