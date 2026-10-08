# VCPG specification

What the app does, flow by flow. This is the source of truth for behaviour. Agent details are in [AGENTS.md](AGENTS.md), storage and modules in [ARCHITECTURE.md](ARCHITECTURE.md), visuals in [DESIGN.md](DESIGN.md).

## 1. Who it is for

One user (the owner), on their own machine. No accounts, no sharing, no hosting. The user wants to finish projects they can defend in an AI-engineering interview, so every feature serves two goals: working code, and the user being able to explain it.

## 2. Glossary

| Term | Meaning |
|---|---|
| Project | One thing being built, with its own git workspace |
| Step | One unit of the plan (for example "KNN recommender core"); each step produces one slide |
| Spine | The fixed step types every plan starts from |
| Gate | The interview that must be passed before a step unlocks the next |
| Rubric | The hidden list of points the user must cover to pass a gate |
| Dossier | A compressed markdown summary of a finished project, used for mock interviews |
| Build crew | Planner, tutor, builder, reviewer, interviewer, grader, slide writer |
| Audit crew | Rook, Bolt, Echo, Pixel: agents that audit the app itself |

## 3. Starting a project

The start screen offers three paths (prototype: `Ideas.dc.html`).

### 3.1 I have a plan

The user describes what they want to build in a text box (goal, rough features, any stack preferences). The planner asks up to three clarifying questions in one batch if something important is missing (data source, how it will be used, constraints), then drafts the plan (section 4).

### 3.2 Give me ideas

1. The user types a topic ("RAG and vectors") and optionally answers two quick chips: *How do you want to use it?* and *Where does the data come from?* (choices like files I upload, a public dataset, a folder on disk).
2. The idea generator returns four project cards. Each card has a name, a one-line pitch, a small thumbnail showing the project in use (a fixed template filled with example content, see DESIGN.md section 7; no image generation), difficulty (*Gentle*, *Medium*, *Stretch*), step count, and the 3 to 5 concepts it teaches, each marked *new*, *know the basics* or *used it before* from the user's history.
3. Clicking a card expands it to show a longer pitch, the proposed architecture (a strip of chained component blocks), the concepts, and *What you will be asked*: sample interview questions.
4. *Build this* hands the card to the planner as the brief. *Teach me first* opens a lesson path for the card's new concepts, then returns to the card.

### 3.3 Teach me a concept

The user names a concept; the tutor builds a lesson path from zero (section 9). When finished the user can start a project that uses it, through *Give me ideas* seeded with the concept.

## 4. Planning

The planner turns the brief into an ordered list of steps.

- **Spine:** mission, architecture, data, core logic, interface, evaluation. Every project starts from these six.
- **Modules:** the planner adds steps the project needs (for example retrieval, auth, background jobs, deployment) and may merge or skip spine steps that do not apply, with a one-line reason for each change.
- Each step has: title, component (frontend, backend, data, LLM, infra, evaluation), goal, the concepts it teaches, files expected to change, acceptance criteria for the code, and a rubric of 3 to 5 points for the gate.
- Typical plans have 5 to 9 steps. More than 10 means the project is too big; the planner says so and proposes a smaller first version.
- The user sees the plan, can reorder, rename, drop or ask for changes in plain words, and must approve it before step 1 starts. Rubrics are hidden from the user; only step titles, goals and concepts are shown.
- The planner may revise later steps when a step's build reveals something (for example a library does not work). Revisions are shown to the user as a diff and need approval. Passed steps are never rewritten.

## 5. The step loop

Each step moves through fixed states. The orchestrator is plain code; agents never decide what state comes next.

```
planned → taught → built → reviewed → toured → interviewing → passed → slide_done
```

### 5.1 Teach (tutor)

Before any code exists, the tutor explains the step: what it will build, why, the key concepts, the options considered and why this one was chosen, and what could go wrong. It uses short sections, small diagrams (mermaid) where they help, and examples tied to this project. The user can ask questions in a side chat; answers are grounded in the plan and, where relevant, the lesson sources. The user clicks *Ready, build it* to continue.

### 5.2 Build (builder)

The builder writes the code for the step in the project workspace through the Agent SDK. Rules:

- Lean and readable: the shortest clear solution; no unused abstractions or speculative options.
- Follows the step's acceptance criteria and the files listed; touching other files needs a reason in the build note.
- Writes or updates tests for the step's real behaviour.
- Ends with a build note: files changed, what each change does, decisions made, anything it could not do.

The console streams the builder's actions live (file edits, commands). The user can pause or stop the build. Stopping keeps the workspace as it is and returns the step to `taught`.

### 5.3 Review (reviewer)

The reviewer checks the builder's work in the sandbox:

- Runs the test suite and the step's mock trials (small realistic runs, for example a sample request to the endpoint, or a recommendation for a test user).
- Removes code that does nothing for the step: dead code, duplicated logic, unused parameters, and edge-case handling that no realistic input can reach. Checks stay at boundaries (user input, files, network, model output).
- Fixes bugs it finds, reruns tests, and writes a review note: what it ran, results, what it cut and why, what it fixed.
- If tests still fail after its fixes, the step goes back to the builder once with the failure. A second failure stops the loop and shows the user both notes with a *Retry build* and *Edit plan* choice.

When review passes, the orchestrator commits the step in the project workspace (`step N: <title>`).

### 5.4 Code tour (tutor)

The tutor walks the user through the actual committed diff, file by file, in reading order: what each part does, why it is written that way, how data flows through it, and what the reviewer changed. Each stop shows the code with the relevant lines highlighted. The user can ask about any line. The tour ends with *I'm ready for the interview*.

### 5.5 Gate (interviewer + grader)

- The interviewer asks open questions in the style of an AI-engineering interview, one at a time, aimed at the step's rubric (for example "Why normalize ratings before measuring distance?"). It never reveals the rubric.
- The user types answers. There is no voice input.
- After each answer the grader scores every rubric item as `covered`, `partial` or `missing`, quoting the user's words as evidence. The gate state is computed in code from the grader's output; the grader does not decide pass or fail.
- **Pass:** every rubric item is `covered` (across the whole gate conversation, not one answer).
- **Hints:** after an answer that leaves items `partial` or `missing`, the user can ask for a hint. Hints come in order: a nudge, then a narrower question, then a worked pointer to the relevant code; further hints stay at the code pointer. The ladder starts again after an answer that raises any item. Hints never state the answer.
- **Re-teach:** after three answers in a row that raise no rubric item (counted since the last re-teach), or whenever the user clicks *Teach me this again*, the tutor re-teaches the missing items with a new explanation and a fresh angle, then the interview resumes with new questions.
- There is no limit on attempts and no way to skip. The step stays locked until it passes.
- The panel shows rubric progress as a count (for example *2 of 4 points covered*), not the items themselves.

### 5.6 Slide (slide writer)

When the gate passes, the slide writer creates one interview slide for the step's component. A slide holds: title, what the component does (one line), a visual (diagram, small chart, or code excerpt chosen from the slide visual kinds in DESIGN.md), 2 to 4 decisions with trade-offs, how it fails or would scale, and the questions the user struggled with at the gate (with hint counts). Speaker notes hold a short spoken explanation in the user's own words, built from their best gate answers.

### 5.7 Step complete

The step is marked done, the next step unlocks, and mission control animates the hand-off. Earlier steps are not re-tested during the project.

## 6. End of project

After the last step passes:

1. **Final review.** The reviewer runs the whole test suite and a full end-to-end mock trial of the finished app.
2. **Re-test.** A short combined gate covering earlier steps: one question per step, focused on the items that needed hints. Same grading rules; a miss triggers a re-teach for that step only.
3. **Deck** (section 7).
4. **README** (section 8).
5. **Dossier and archive** (section 10).

## 7. Deck and export

- The deck is assembled from the step slides plus three generated slides: title (project name, one-liner, stack), architecture overview (whole-system diagram), and retrospective (*what I would do differently*, *questions I prepared for*).
- The deck viewer shows slides with speaker notes, lets the user reorder slides and edit text inline, and regenerate one slide with an instruction.
- **Export:** PowerPoint (`.pptx`, via python-pptx) and PDF. Diagrams and charts are rendered to images for the export. The export keeps speaker notes.
- Every export is stored with the project as a version (`deck_v1.pptx`, `deck_v2.pptx`, ...) and is downloadable from the deck viewer and the archive.

## 8. README

The user writes the README; the app does not write it for them.

1. **Template.** The README coach generates a `README.md` template for this project with these sections: title and one-liner, demo, why I built it, how it works, architecture, key decisions, results, how to run it, limitations and next steps, what I learned. Each section contains an HTML comment telling the user what to write there (for example `<!-- Write two sentences on why cosine similarity fit your data. Mention mean-centering. -->`).
2. **Auto-inserted parts.** Diagrams (architecture mermaid from the plan, data flow), the run commands, and the stack list are inserted automatically and marked as generated.
3. **Editor.** A split view: markdown editor on the left, rendered preview on the right.
4. **Coach review.** On *Ask the coach to review*, the coach checks every claim against the actual project (code, plan, test results, gate answers) and returns a list of notes, each tagged `does not match`, `gap` (a required section is thin or missing), or `unclear`, with the line it refers to and what the project actually shows. The coach never rewrites the text; it points and explains.
5. The user edits and asks again as many times as needed. The README is *ready* when the coach returns no `does not match` or `gap` notes. The README is then committed to the project workspace.

## 9. Lessons

Prototype: `Lesson.dc.html`.

### 9.1 Sources

- **Trusted sources** (used for claims): textbooks, papers, lecture notes and official documentation. The user can add their own (PDF, markdown, URL). The app also keeps a seeded list of open sources per topic, fetched on demand.
- **Community sources** (used for context only): blog posts, forum threads, social media posts. They may supply examples, analogies and "how people use this in practice", shown in a block labelled *Community*, and never support a factual claim.
- Sources are split into passages, embedded and stored. Retrieval returns passages with stable IDs.

### 9.2 Grounding rule

Every factual sentence in a lesson cites one or more trusted passage IDs. A deterministic validator (code, not an LLM) rejects a lesson section when:

- a paragraph has no citation, or cites an ID that was not retrieved for this lesson;
- a citation points to a community source;
- a key term in the paragraph (from the concept's term list) does not appear in any cited passage.

Rejected sections are regenerated with the validator's errors, up to twice; after that the section is dropped and the lesson shows a short note that the topic needs a source. Citations render as small numbered chips that open the passage.

### 9.3 Lesson shape

A lesson path is 4 to 8 lessons ordered from zero to the concept the project needs. Each lesson has the sections *Start here*, *See it* (a diagram or interactive visual), *Worked example* (code snippet with explanation), *Check yourself*, *Your turn*, and *Recap*, plus a *By the end you can* list.

- Written for someone with no CS background, defining every term before it is used, but going deep enough to answer interview questions.
- Question types: multiple choice, true or false, short answer (graded by the grader against a mini rubric), and write code (run against tests in the sandbox).
- Wrong answers explain why, using the misconception the option represents.

## 10. Archive, dossier and mock interviews

Prototype: `Archive.dc.html`.

- When a project finishes (README ready), the dossier writer compresses it into a markdown dossier of about 1,500 words: mission, architecture, each component's decisions and trade-offs, results with numbers, failure modes and scaling notes, the user's strongest answers (quoted), and the items that needed hints.
- The archive lists finished projects with stack, date, deck and README links, and the dossier.
- **Mock interview:** unlocks when a project is finished and its README passes review. The user picks a length (10, 20 or 30 minutes) and a focus (project deep dive, system design, behavioral). The interviewer runs a timed interview from the dossier only, with follow-up questions that dig into answers. The grader keeps a live scorecard on four dimensions: system design, failure modes, motivation and impact, communication. *End and score* shows the scorecard with evidence quotes and two or three things to practise. Mock interview transcripts and scores are stored with the project.

## 11. Squad screen

Prototype: `Squad.dc.html`. A game-style loadout screen for every agent (build crew, audit crew, helpers).

- Each agent card shows its pixel character, role, current model and effort, and whether it runs on the API or the Agent SDK.
- The user picks a model (Opus, Sonnet, Haiku) and an effort (`medium`, `high`, `xhigh`, `max`). `low` is not offered.
- A *relative profile* bar chart shows how the choice compares on depth and speed, as rough relative bars (no prices, no token counts).
- Cards show *recommended* or *custom*. *Reset to recommended* restores `config/agents.yaml`. *Save loadout* writes overrides to the database; they apply to the next call.

## 12. Core access

Prototype: `MissionControl.dc.html`. Clicking the core in mission control enlarges it into an overlay with:

- **Anthropic API key:** paste, test (one tiny call), save to the OS keychain. Shown masked with the last four characters.
- **GitHub token:** paste, test (reads the repo and checks the token's permissions), save to the keychain. The panel shows which permissions were found and warns if any are broader than *Contents* and *Pull requests* read/write on the vcpg repo. Admin or delete permissions block saving.
- Status lights for each, and *Remove*.
- Links to Squad and Archive.

## 13. Audit crew

Prototypes: `Audit.dc.html`, `AuditPopups.dc.html`.

### 13.1 Triggers

- **Project scan (quick):** runs automatically after each project finishes. Covers that project's agent logs only.
- **Deep scan:** runs every 14 days when the app is open (or on next launch if missed), and on demand from the audit bay. Covers all logs since the last deep scan plus the calibration test sets.

### 13.2 What they check

| Agent | Checks |
|---|---|
| Bolt | Planner plans (needless replans, steps too big), builder code (bloat, ignored acceptance criteria), reviewer cuts (cuts that broke things, dead code left in) |
| Echo | Tutor explanations, lesson grounding failures, quiz quality, interviewer questions (hint leaks, off-rubric questions), grader calibration drift |
| Pixel | Slides versus code (claims the code does not support), deck formatting, README coach notes that were wrong |
| Rook | Reads the three reports, traces root causes across them, decides which fixes are worth a pull request, writes them |

### 13.3 Output

- An issue board with severity (red siren for high), evidence (log excerpts), and the agent that found it.
- For each fix, a pull request on the vcpg repo: title, problem, evidence, the change, and before/after results on the relevant test set.
- Fixes are usually prompt or rubric-template changes; code changes are allowed for clear bugs.
- **Auto-merge:** only changes that pass every rule in [SECURITY.md](SECURITY.md) section 6. Everything else waits for the user's review in GitHub.

### 13.4 Mission control indicator

A small pill in the corner of mission control shows the audit state: *Offline* (crew asleep at their stations), *Project scan* (smaller popup, count of issues and fixes), or *Deep scan* (bigger and louder: the full crew, a radar sweep, and live counts). Clicking it opens the audit bay.

## 14. Mission control

Prototype: `MissionControl.dc.html`. The home screen while a project is active:

- The orchestrator core (blob) in the centre with links to each build-crew agent; links pulse when an agent is working; the cyan state shows when it is the user's turn.
- The step list with states and the current step's phase.
- The live console streaming agent events.
- The current panel (teach, build log, review, tour, gate, slide) on the right.
- The audit pill, Squad and Archive links.

## 15. Out of scope

- Multiple users, login, cloud hosting, or syncing.
- Voice input or output.
- Non-Claude models.
- Token budgets, cost tracking, or spend caps.
- Deploying the generated projects anywhere.
- Mobile layout (desktop browser only, minimum 1280px wide).
