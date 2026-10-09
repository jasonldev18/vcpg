# Handoff: VCPG build, paused mid-Phase 8

Read `CLAUDE.md` first, then this file. It records where the build stopped, what is uncommitted, what the user decided along the way, and what is left.

## Where things stand

- **Branch:** `phase-8`. Each phase has its own branch (`phase-0` to `phase-8`), stacked on the previous one.
- **`main`:** local only, never pushed. It has been fast-forwarded to the end of Phase 7 (`0061730`). Fast-forward it again when Phase 8 is done: `git fetch . phase-8:main`.
- **Nothing has been pushed to GitHub, and no pull requests have been opened.**
- **Phases 0 to 7 are complete.** Every automated and live acceptance check for them passed. The manual checks are listed under "Left for the user" below.
- **Phase 8 is about half done.**

## User decisions to keep following

- The user asked to continue through all phases without stopping between them, unless something goes wrong. Show the plan at the start of each phase, then build.
- Live tests (`make live`) cost money. The user approved running them, and they have run at the end of each phase.
- **Never open real GitHub pull requests or push.** The Phase 7 manual check (a deep scan opening a PR) needs the user's GitHub token and is the user's to run.
- The user's terminal is **PowerShell on Windows**. `make` is installed with winget (`ezwinports.make`), and Python 3.12 is used through `py -3.12`. In Git Bash, put make on PATH with `export PATH="$LOCALAPPDATA/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$PATH"`.
- Unbuilt screens are greyed out in the nav with "Phase N" (the `phase` field in `frontend/src/screens.ts`). Remove the field when a screen ships. Only Squad (`/squad`) is still marked; it ships in Phase 8.
- The user said **not** to keep the lesson and tutor chat visible after "Ready, build it". Don't add that.

## Uncommitted work (Phase 8, Squad screen)

These files exist but were **never type-checked, linted or tested**. The session was paused mid-command, so verify them first:

- `frontend/src/scenes/suits.ts` (new): the audit crew's suited pixel figure (`drawSuit`, `LOOKS`, `CODES`), ported from `Squad.dc.html`'s `fig`. The audit bay pixel room will reuse it.
- `frontend/src/screens/Squad.tsx` (new): the Squad loadout screen. It has crew tabs (Build crew, Audit crew, Helpers), an agent list, model cards, effort buttons (**medium, high, xhigh and max only; never low**), and relative profile bars for **depth and speed only** (the prototype's Cost bar is left out on purpose: no cost features). It also has tools, Save loadout, Reset to recommended, and a pixel portrait canvas.
- `frontend/src/api/types.ts`: adds the `SquadMember` type.
- `frontend/src/routes.tsx` and `screens.ts`: wire `/squad` to `<Squad />` and remove its `phase: 8` marker.
- `frontend/src/shell.css`: Squad styles (`.squad`, `.frame`, `.agent-row`, `.hex`, `.pill`, `.mcard`, `.eff`, `.profile`, `.segs`, `.portrait`, `.badge`, `.facts`).

Next steps for this work:

1. In `frontend/`, run `npx prettier --write src`, then `npx tsc -b`, `npx eslint .` and `npx vitest run`, and fix any errors.
2. The shell test (`src/routes.test.tsx`) renders every screen. It now needs a fake for `GET /api/squad`, returning a list of `SquadMember`.
3. Add `src/screens/Squad.test.tsx`. It should check that the list loads, picking a model or effort marks the agent custom, `low` is never offered, Save sends `PUT /api/squad` with every agent, and Reset restores the recommended pair.
4. Commit.

The backend for Squad is done and committed: `backend/routes/squad.py`, `GET/PUT /api/squad`, with tests in `tests/test_llm_config.py`.

## Phase 8 remaining (docs/BUILD_PLAN.md)

Done and committed:
- Motes background with cursor ripple (`scenes/Background.tsx`).
- Panel tilt, sheen and corner, and the cursor glow (`theme/tokens.css`).
- The orchestrator stage (`scenes/CoreNetwork.tsx`): blob core, agent links, comet trails, and the pixel build crew with blink, bob, hop and sparks (`scenes/sprites.ts`). It's driven by the agents running in the event stream, and the cyan "your turn" state shows when nothing is running.
- Clicking the core opens Core access through the `OpenCore` context (`src/coreContext.ts`). The core grows into the overlay with a Motion `layoutId="core"` spring.
- Panel enter and exit transitions in mission control (Motion, 220ms).
- A reduced-motion CSS override and the `useReducedMotion` and `useFrame` helpers (`scenes/canvas.ts`). Canvases draw one still frame under reduced motion.

Still to do:
1. Finish Squad (above).
2. **Audit bay full-screen pixel room**, ported from `design/prototypes/Audit.dc.html` (`drawAgent`, `poseOf`; about 62KB, not read yet). It needs consoles, the intel board with a siren and screen shake on high-severity issues, a repair bay, a glass test chamber, the PR board stamped READY TO REVIEW or MERGED, and the AUDIT CORE holo table with a radar sweep. It has offline, project-scan and deep-scan modes, hover dossier cards, and click-to-open details. Status text is in Silkscreen. Replace the plain `screens/AuditBay.tsx` view, keeping its data and tests. Data comes from `GET /api/audit`, plus events on channel `-1` (`audit_update`, `audit_siren`).
3. **Audit pill popups**, from `AuditPopups.dc.html`: the offline, project-scan and deep-scan states. The pill is `AuditPill` in `screens/AuditBay.tsx`.
4. Style the idea card thumbnails (`components/IdeaCard.tsx`, `.th` CSS) and the slide visuals (`components/SlideView.tsx`) to match `Ideas.dc.html` and the three `Slide*.dc.html` prototypes.
5. The step hand-off animation: a finished step's chip flies to a deck counter (DESIGN 3.4). This hasn't been started.
6. An accessibility pass (DESIGN 8): every canvas gets an `aria-label`, and every canvas-only state also shows as text. The stage and Squad portrait already have labels. Check keyboard use and focus rings.
7. Phase 8 docs: update ARCHITECTURE and DESIGN where the implementation differs. Then run `make lint` and `make test`, fast-forward `main`, and report.
8. Phase 8's acceptance checks are visual (matching the prototypes, 60fps, reduced motion), so the user does them in the browser. No browser tool was available in this session.

## Problems found and fixed during the build

Don't reintroduce these:
- `.gitignore` had `exports/`, which ignored `backend/exports/`, so the export code was never committed. The data-folder patterns are now anchored (`/exports/`, `/workspaces/`, `/logs/`). Check `git status --ignored` after adding a new package.
- On Windows, the venv sandbox **must keep `SYSTEMROOT`**. Without it, even `import asyncio` fails. As a result, the venv fallback has no network isolation; only Docker does, and the build panel says so. Docker isn't installed on this machine.
- Git object files are read-only on Windows. Delete scratch clones with `git.remove_clone`, never plain `shutil.rmtree`.
- Structured outputs: a schema with a union of five typed visual specs was rejected ("compiled grammar is too large"). The slide writer now returns `visual.spec_json` as JSON text, and `SlideDraft` validates it. Check new schemas against the real API early.
- Agent SDK sessions: the guard must allow the SDK's internal `StructuredOutput` tool. Read-only audit sessions deny Bash and sandbox calls in the guard itself.
- Shell gotcha: in this environment, Python heredocs in Bash turn `\n` into real newlines. Use the Write or Edit tools for code containing escapes. Python's `write_text` on Windows writes CRLF; git normalizes it, but Prettier may complain until `--write` runs.

## How things are built (quick map)

- **Backend** (`backend/`): FastAPI on 127.0.0.1:8000 with a per-launch token for non-GET requests. stdlib `sqlite3` with numbered migrations (`backend/migrations/001` to `007`). All Claude calls go through `backend/llm/`: `client.py` for the Messages API and `sdk.py` for Agent SDK sessions. Sessions go through a loopback key proxy (`proxy.py`), so the CLI never holds the API key, and the `guard.py` PreToolUse rules apply.
- **Orchestration** (`backend/orchestrator/`): `machine.py`, `planning.py`, `runner.py` (teach, chat, tour, gate), `build.py` (background build, review, retry, blocked), `project_end.py` (slide on pass, final review, re-test, deck), `slides.py`, `wrapup.py` (README coach, dossier), `mock.py`, `ideas.py`.
- **Lessons** (`backend/lessons/`): sources with fastembed embeddings, retrieval, the deterministic citation validator, and the builder.
- **Audit** (`backend/audit/`): `policy.py` and `secrets_scan.py` (one test per SECURITY 6 rule), `github.py` (API-only branches, commits, PRs and merges; never git push), `testsets.py` (calibration scoring shared with `make live`), and `runner.py` (scouts, Rook, the 14-day scheduler).
- **Frontend** (`frontend/src/`): React with strict TypeScript, routes in `routes.tsx`, screens in `screens/`, canvas scenes in `scenes/`, and the API client and SSE hook in `api/`.
- **Tests:** `make test` runs 308 backend tests and 46 frontend tests, all passing at the last commit. Agent replies are faked with recorded fixtures (`tests/conftest.py` has `FakeLLM` and `FakeBuilder`, and `tests/journeys.py` has shared flows). `make live` runs the real API calibrations: grader agreement 97 to 98%, reviewer, slides, README, lessons, a live builder and the dossier. All passed.

## Left for the user (manual acceptance checks)

- **Phase 1:** plan a small project and pass step 1's gate by typing. Confirm hints arrive in order and that "Teach me this again" gives a different explanation.
- **Phase 2:** watch a real build in the app, including stop and pause.
- **Phase 3:** run one project of at least 4 steps end to end.
- **Phase 4:** confirm the exported `.pptx` opens in PowerPoint and LibreOffice.
- **Phase 5:** confirm a mock interview stays within its length and the scorecard quotes your answers.
- **Phase 6:** run "Teach me first" and return to the card, and confirm "Build this" creates a plan.
- **Phase 7:** save a fine-grained GitHub token in Core access, then run a deep scan on real logs and check that it opens at least one PR.
- **Phase 8:** compare the screens side by side with the prototypes, check that reduced motion leaves only fades, and confirm 60fps.

The user's existing project database is at `~/.vcpg/vcpg.db`. It holds an Apple Watch project from Phase 1. Migration 003 reset its placeholder build back to teaching.
