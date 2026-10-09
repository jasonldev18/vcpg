# Handoff: VCPG build, all phases complete

Read `CLAUDE.md` first, then this file.

## Where things stand

- **Phases 0 to 8 are built.** Every automated acceptance check passes: `make lint` is clean, `make test` runs 309 backend tests and 50 frontend tests.
- **`main`** is local only, never pushed. It was fast-forwarded to the end of Phase 8.
- **Nothing has been pushed to GitHub, and no pull requests have been opened.**
- What is left are the manual checks under "Left for the user" below; Phase 8's are visual and need a browser.

## User decisions to keep following

- The user asked to continue through all phases without stopping between them, unless something goes wrong. Show the plan at the start of each phase, then build.
- Live tests (`make live`) cost money. The user approved running them, and they have run at the end of each phase.
- **Never open real GitHub pull requests or push.** The Phase 7 manual check (a deep scan opening a PR) needs the user's GitHub token and is the user's to run.
- The user's terminal is **PowerShell on Windows**. `make` is installed with winget (`ezwinports.make`), and Python 3.12 is used through `py -3.12`. In Git Bash, put make on PATH with `export PATH="$LOCALAPPDATA/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$PATH"`.
- Unbuilt screens were greyed out in the nav with "Phase N" (the `phase` field in `frontend/src/screens.ts`). Every screen has shipped now.
- The user said **not** to keep the lesson and tutor chat visible after "Ready, build it". Don't add that.

## Phase 8 summary

- Motes background, panel tilt and sheen, the orchestrator stage with the pixel build crew, and Core access opening from the core.
- Squad loadout screen (medium to max effort only; depth and speed bars, no cost bar).
- Audit bay pixel room (`scenes/auditRoom.ts`, ported from `Audit.dc.html`), driven by `GET /api/audit` and the channel -1 events. The choreography is ambient per mode; the boards, the mode and the siren are real.
- Audit pill popups (offline, project scan, deep scan with live counts).
- Idea thumbnails and slide visuals styled to the prototypes.
- Step hand-off: the finished step's chip flies into the deck counter. `MotionConfig reducedMotion="user"` wraps the app.
- Accessibility: every canvas has a label and a text equivalent; low-contrast `--dim` text now uses `--mute`.

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
- **Tests:** `make test` runs 309 backend tests and 50 frontend tests, all passing at the last commit. Agent replies are faked with recorded fixtures (`tests/conftest.py` has `FakeLLM` and `FakeBuilder`, and `tests/journeys.py` has shared flows). `make live` runs the real API calibrations: grader agreement 97 to 98%, reviewer, slides, README, lessons, a live builder and the dossier. All passed.

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
