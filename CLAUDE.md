# CLAUDE.md

Instructions for Claude Code when building VCPG. Read this file first, every session.

## What you are building

VCPG is a local web app that builds a software project with a crew of Claude agents and teaches the user every step, locking progress behind an interview gate until the user can explain it. The full picture is in the docs below. Do not invent features that are not in them; if something is missing or contradictory, stop and ask.

## Read in this order

1. `README.md`: the one-page overview
2. `docs/SPEC.md`: what the app does, flow by flow (the source of truth for behaviour)
3. `docs/ARCHITECTURE.md`: stack, module layout, state machine, data model
4. `docs/AGENTS.md`: every agent's job, inputs, outputs, JSON schemas and rules
5. `docs/SECURITY.md`: keys, sandbox, agent permissions, auto-merge rules (non-negotiable)
6. `docs/DESIGN.md`: theme tokens, motion, screens, pixel characters
7. `docs/BUILD_PLAN.md`: phases and acceptance checks
8. `config/agents.yaml`: default model, effort and runtime per agent

## How to work

- Build **one phase at a time** from `docs/BUILD_PLAN.md`, in order. Do not start a phase until the previous phase's acceptance checks pass.
- At the start of a phase, write a short plan (files to add, tests to write) and show it to the user before coding.
- At the end of a phase, run every acceptance check for that phase, report the results, and wait for the user before moving on.
- Commit after each working sub-step with a clear message. Keep commits small.
- Keep `docs/` in sync. If you change behaviour, update the doc in the same commit.

## Code rules

The app teaches lean code, so its own code must be lean.

- Write the shortest readable version that is correct. If 30 lines do the job, do not write 50.
- Validate at boundaries (HTTP input, LLM output, file and subprocess results). Do not add defensive branches for states that cannot happen inside the program.
- No speculative abstractions, plugin systems, or config options nobody asked for.
- Names over comments. Comment only the why, never the what.
- Every module gets tests for its real behaviour. No tests that only assert mocks were called.

### Backend

- Python 3.12, FastAPI, SQLite (stdlib `sqlite3` or SQLModel, pick one and stay with it), Pydantic v2 for every request, response and LLM JSON schema.
- Format and lint with `ruff`; type check with `mypy --strict` on `backend/`.
- Tests with `pytest`. LLM calls are faked in unit tests with recorded fixtures; one opt-in `pytest -m live` suite hits the real API.
- All LLM calls go through `backend/llm/` (see ARCHITECTURE). No other module imports `anthropic` or `claude_agent_sdk` directly.

### Frontend

- React, TypeScript with `strict: true`, Vite. Plain CSS with custom properties for tokens (from `docs/DESIGN.md`), no CSS framework.
- Canvas 2D for animated scenes, Motion for UI transitions. No other animation library without asking.
- Lint with ESLint and format with Prettier. Component tests with Vitest and Testing Library.

### Prompts

- Every agent prompt lives in `prompts/<agent>.md`, never inline in code. Load by name.
- Every structured output has a Pydantic model and a JSON schema; parse and validate, and retry once with the validation error on failure.

## Models

- Only Claude models. Defaults are in `config/agents.yaml`; the user overrides them on the Squad screen.
- Model IDs: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`.
- Effort is never below `medium`. The Squad screen must not offer `low`.
- There is no token budget and no cost cap feature. Do not add one.

## Safety rules (always)

- Never write a key or token to a file, log, commit, database row, or error message. Secrets live in the OS keychain via `keyring` only.
- The server binds to `127.0.0.1` only.
- Generated project code runs only inside the sandbox described in `docs/SECURITY.md`.
- Never run destructive or irreversible git commands (`reset --hard`, `rebase`, `push --force`, `branch -D`, `clean -fd`, `checkout -- .`, aborting a merge or rebase) without first explaining the risk to the user and getting a yes. This applies to the vcpg repo and to project workspaces.
- Do not change `docs/SECURITY.md` rules or the auto-merge allowlist without the user asking.

## Design prototypes

`design/prototypes/*.dc.html` are the visual reference for each screen (layout, colors, motion code). They were made in a design canvas and need its runtime to play, so treat them as source to read, not pages to ship. Port their canvas drawing code into React components. Only the Solar theme and the blob core ship; ignore the other theme and core options left in `MissionControl.dc.html`.
