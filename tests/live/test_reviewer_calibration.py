"""Live: on calibration/reviewer/, every planted unreachable branch is cut and every real
boundary check is kept, by the real reviewer, through the same task the app builds."""

import asyncio
import shutil

import pytest

from backend import db, secrets
from backend.llm import sdk
from backend.orchestrator.context import tag
from backend.schemas import ReviewNote
from backend.workspace import git, sandbox
from tests.calibration import ReviewerCase, reviewer_cases

pytestmark = pytest.mark.live


async def review(
    project_id: int, name: str, case: ReviewerCase
) -> tuple[ReviewNote, dict[str, str]]:
    with db.session() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, brief, start_path) VALUES (?, ?, 'x', 'plan')",
            (project_id, name),
        )
        step_id = conn.execute(
            "INSERT INTO steps (project_id, position, title, component, goal)"
            " VALUES (?, 0, ?, 'backend', ?)",
            (project_id, case.step.title, case.step.goal),
        ).lastrowid
    repo = git.init(project_id, name)
    base = git.head(repo)
    for path in case.files:
        shutil.copy(path, repo / path.name)
    await sandbox.run(project_id, "pip install -q pytest", allow_install=True)
    step = tag(
        "step",
        f"Title: {case.step.title}\nGoal: {case.step.goal}\nFiles: {', '.join(case.step.files)}\n"
        "Acceptance:\n" + "\n".join(f"- {a}" for a in case.step.acceptance),
    )
    task = "\n\n".join(
        [step, tag("build_note", case.build_note), tag("diff", git.diff_since(repo, base))]
    )
    go = asyncio.Event()
    go.set()
    note = await sdk.run_agent(
        "reviewer", task, repo, ReviewNote,
        project_id=project_id, step_id=step_id or 0, allow_install=False, resume=go,
    )  # fmt: skip
    after = {
        p.name: (repo / p.name).read_text(encoding="utf-8")
        for p in case.files
        if (repo / p.name).exists()
    }
    return note, after


async def test_reviewer_cuts_unreachable_code_and_keeps_boundaries() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    cases = reviewer_cases()
    results = await asyncio.gather(
        *(review(100 + i, name, case) for i, (name, case) in enumerate(cases.items()))
    )
    problems = []
    for (name, case), (note, after) in zip(cases.items(), results, strict=True):
        print(f"\n{name}: status {note.status}")
        for cut in note.cut:
            print(f"  cut {cut.path}: {cut.what} ({cut.why})")
        for m in case.unreachable:
            if m.marker in after.get(m.file, ""):
                problems.append(f"{name}: kept unreachable {m.marker}")
        for m in case.boundary:
            if m.marker not in after.get(m.file, ""):
                problems.append(f"{name}: cut boundary check {m.marker}")
        if note.status != "pass":
            problems.append(f"{name}: review status {note.status}: {note.failure}")
    print("\n".join(problems) or "\nall planted branches cut, all boundaries kept")
    assert not problems
