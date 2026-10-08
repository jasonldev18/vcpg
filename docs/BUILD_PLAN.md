# Build plan

Build in this order. Each phase ends with acceptance checks; do not start the next phase until they pass and the user has seen the result. Each phase should leave the app runnable.

The first usable milestone is the end of phase 3: a real project can be planned, taught, built, reviewed, toured and gated end to end. Everything after that adds outputs, discovery, self-improvement and polish.

## Phase 0: Scaffold

- Repo layout from ARCHITECTURE section 2; `pyproject.toml` (ruff, mypy, pytest), `frontend/` with Vite + React + TS strict, ESLint, Prettier, Vitest.
- `Makefile`: `setup`, `dev` (API and UI together), `test`, `lint`, `live` (opt-in live LLM tests).
- FastAPI app bound to 127.0.0.1 with a health route, per-launch API token, CORS for the UI origin.
- SQLite schema from ARCHITECTURE section 4 with a simple migration step (numbered SQL files).
- `secrets.py` on `keyring`; the log redaction filter (SECURITY section 2) with tests.
- `llm/config.py` reading `config/agents.yaml` + overrides; rejects effort below `medium`.
- Theme tokens CSS and fonts; an empty app shell with routes for every screen.
- GitHub Actions: lint and unit tests on pull requests (no secrets used in CI).

**Acceptance**
- `make setup && make dev` starts both servers on 127.0.0.1 only; `make test` and `make lint` pass.
- Redaction test: a log line containing a fake `sk-ant-...` key and the stored value is written redacted.
- Config test: an override of `effort: low` is rejected.

## Phase 1: Teaching loop and gate (no code generation yet)

- `llm/client.py` with logging to `agent_calls`, JSON schema parsing with one retry, streaming to the event bus.
- Prompts: planner, tutor (teach, chat, reteach), interviewer, grader.
- Orchestrator state machine (`machine.py`) with the full transition table and tests for every allowed and disallowed transition.
- Plan flow: brief → clarifying questions → plan → user edits → approve.
- Teach panel, tutor side chat.
- Gate: interviewer turns, grader JSON, `gate/rubric.py` (merge, verbatim evidence check, pass rule), hint ladder, re-teach after three non-improving answers or on request, progress shown as counts only.
- For this phase, *build*, *review* and *tour* are stubbed: the step jumps from `taught` to `toured` with a placeholder.
- SSE events endpoint and the mission control shell: step list, current panel, console (static layout, no canvas animation yet).
- Core access overlay (plain version): save, test and remove the Anthropic key.
- Calibration set `calibration/gate/` with at least 3 rubrics × 6 graded answers.

**Acceptance**
- Unit: rubric merge never lowers a status; an evidence quote not found in the user's messages becomes `missing`; the gate opens only when every item is `covered`.
- Live (`make live`): grader calibration agrees with expected statuses on at least 90% of items.
- Manual: plan a small project, pass step 1's gate by typing answers; hints appear in ladder order and never state the answer; *Teach me this again* produces a different explanation.

## Phase 2: Builder and workspaces

- `workspace/git.py`: init per project at plan approval, commit by the orchestrator only.
- `workspace/sandbox.py` with Docker and the venv fallback; `run_in_sandbox` custom tool.
- `llm/sdk.py`: Agent SDK sessions with `setting_sources=[]`, allowed and denied tools, `PreToolUse` guard (SECURITY section 4).
- Builder prompt and build note; live console streaming of tool use; pause and stop.

**Acceptance**
- Guard tests: attempts to write outside the workspace, write into `.git/`, run `git push`, `git reset`, `curl`, `printenv`, or read `~/.ssh` are all denied.
- Sandbox tests: network is off by default; a package install works only through the allowed pattern; the environment contains no secrets.
- Manual: the builder completes a small step in a real project; the console shows file edits live; stopping returns the step to `taught` with files intact.

## Phase 3: Reviewer and code tour

- Reviewer prompt with the reachability rule; review note; builder retry once on failure; `blocked` state with *Retry build* / *Edit plan*.
- Orchestrator commit after review passes.
- Tutor `tour` mode reading `git show`; code tour UI with highlighted ranges and per-line questions.
- Calibration set `calibration/reviewer/`: small repos with planted dead code, unreachable branches, and real boundary checks.

**Acceptance**
- Live: on the reviewer calibration set, every planted unreachable branch is cut and every real boundary check is kept.
- Manual: one full project of at least 4 steps runs end to end through teach, build, review, tour, gate. Each step has a commit in the workspace.

## Phase 4: Slides and deck export

- Slide writer prompt and schema; slide rendering in the app for every visual kind (DESIGN section 6).
- End-of-project flow: final review, re-test gate, title / overview / retrospective slides.
- Deck viewer: reorder, inline edit, regenerate one slide.
- `exports/render.py`, `pptx.py`, `pdf.py`; versioned exports stored per project and downloadable.

**Acceptance**
- The exported `.pptx` opens in PowerPoint and LibreOffice with all slides, visuals as images, and speaker notes.
- The PDF matches the slide order.
- A second export creates `v2` and keeps `v1` downloadable.
- Live: on `calibration/slides/`, no slide makes a claim the step bundle does not support.

## Phase 5: README coach, dossier, archive, mock interview

- README coach `template` and `review` modes; editor with preview; ready state; commit README to the workspace.
- Dossier writer; archive screen with deck and README links.
- Mock interview: length and focus, timer, interviewer from the dossier only, live scorecard, *End and score*, stored transcript.

**Acceptance**
- Live: on `calibration/readme/`, every planted mismatch is flagged `does_not_match` with what the project shows; the coach never returns rewritten README text.
- The dossier for a finished project is under about 1,500 words and every number in it appears in the inputs.
- Manual: the mock interview stays within the chosen length and the scorecard quotes the user's answers.

## Phase 6: Discovery: ideas and lessons

- Idea generator and the start screen (three paths, chips, four idea cards with thumbnails, expanded card, *Build this*, *Teach me first*).
- Sources: upload (PDF, markdown), URL fetch, seeded open sources; passage splitting; local embeddings; retrieval.
- Lesson builder and `lessons/validate.py`; lesson screen with sections, visuals, MC / TF / short / code questions, citation chips, *Community* block.
- Calibration set `calibration/lessons/`.

**Acceptance**
- Validator unit tests: a paragraph with no citation, an unknown passage ID, a community-source citation, or a key term missing from the cited passages is rejected.
- Live: generated lessons for three concepts pass the validator with no dropped sections in at least two of them.
- Manual: *Teach me first* on an idea card runs a lesson path and returns to the card; *Build this* creates a plan from the card.

## Phase 7: Audit crew and pull requests

- GitHub token in Core access with permission check (SECURITY section 3).
- Audit runner: project scan after each project, deep scan every 14 days, manual run.
- Scouts (Bolt, Echo, Pixel) and Rook prompts; reports, issues, fixes on `audit/*` branches, before/after test-set results, pull requests via the GitHub API.
- `audit/policy.py` and `audit/secrets_scan.py` implementing every rule in SECURITY section 6; auto-merge only when all pass.
- Audit bay screen (plain version with issue and PR lists) and the mission control pill.

**Acceptance**
- Policy tests, one per rule: a change touching a blocked path, exceeding the size cap, removing a `never` line, containing a fake key, or worsening one calibration item is not auto-merged. A small allowed wording change that passes everything is.
- The secrets scan catches `sk-ant-`, `github_pat_`, private key headers and high-entropy strings in a diff.
- Token check: a token with Administration permission is refused.
- Manual: a deep scan on seeded bad logs opens at least one pull request with evidence and before/after results.

## Phase 8: Visual polish and animation

- Background motes with cursor ripple, panel tilt and cursor highlight (DESIGN section 3).
- Mission control stage: blob core, agent links, comet trails, pixel build crew; core click to Core access.
- Squad loadout screen with pixel cards and relative profile bars.
- Audit bay full-screen pixel room with suited agents, intel board, siren, repair bay, test chamber, PR board, hover dossiers; popups for offline / project scan / deep scan.
- Idea card thumbnails, slide visuals styled to the prototypes.
- Reduced motion and accessibility pass (DESIGN section 8).

**Acceptance**
- Side by side with each prototype in `design/prototypes/`, layout, colours and motion match.
- With `prefers-reduced-motion`, nothing animates beyond fades.
- Every canvas has an aria label and every canvas-only state is also shown as text.
- Mission control holds 60 fps on a typical laptop with the console streaming.

## After phase 8

Use VCPG to build a real project from start to finish, then let the first project scan run. Fix what it finds before adding anything new.
