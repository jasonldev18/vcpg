"""Live: a real builder session through the key proxy, the guard and the sandbox tool."""

import asyncio

import pytest

from backend import db, secrets
from backend.events import bus
from backend.llm import sdk
from backend.orchestrator.context import tag
from backend.schemas import BuildNote
from backend.workspace import git

pytestmark = pytest.mark.live

TASK = "\n\n".join(
    [
        tag("plan", "Project: Tiny maths\nSteps:\n1. Add helper"),
        tag(
            "step",
            "Title: Add helper\nComponent: backend\nGoal: A function that adds two numbers.\n"
            "Files: maths.py, test_maths.py\nAcceptance:\n"
            "- maths.add(2, 3) returns 5\n- test_maths.py passes under pytest",
        ),
    ]
)


async def test_builder_writes_and_tests_code_in_the_workspace() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    with db.session() as conn:
        pid = conn.execute(
            "INSERT INTO projects (name, brief, start_path) VALUES ('Tiny maths', 'x', 'plan')"
        ).lastrowid
        sid = conn.execute(
            "INSERT INTO steps (project_id, position, title, component, goal)"
            " VALUES (?, 0, 'Add helper', 'backend', 'add')",
            (pid,),
        ).lastrowid
    assert pid and sid
    repo = git.init(pid, "Tiny maths")
    events = bus.subscribe(pid)
    go = asyncio.Event()
    go.set()

    note = await sdk.run_agent(
        "builder", TASK, repo, BuildNote,
        project_id=pid, step_id=sid, allow_install=True, resume=go,
    )  # fmt: skip

    actions = []
    while True:
        try:
            event = await asyncio.wait_for(anext(events), 0.1)
        except TimeoutError:
            break
        if event.type == "tool_use":
            actions.append((event.data["summary"], event.data["denied"]))
    print("\n".join(f"{'DENIED ' if d else ''}{s}" for s, d in actions))
    print(note.model_dump_json(indent=1))
    assert (repo / "maths.py").exists()
    assert any(f.path.endswith("maths.py") for f in note.files)
    assert any(s.startswith("run_in_sandbox") for s, _ in actions), "tests were not run"
    assert not (repo / "pip").exists(), "a cache was written into the workspace"
