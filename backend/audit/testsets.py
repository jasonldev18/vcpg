"""Calibration test sets, scored per item (AGENTS.md "Calibration sets").

Used by `make live` and by audit runs, which score a change before and after on every item
(SECURITY.md section 6, rule 6). Scores are 1.0 for a right result and 0.0 for a wrong one.
Expectations always come from this repo's calibration/ folder, which audits cannot change.
"""

import asyncio
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from fnmatch import fnmatch
from pathlib import Path

import yaml
from pydantic import BaseModel

from backend.gate import rubric
from backend.gate.rubric import Item
from backend.lessons.retrieve import Passage
from backend.lessons.validate import check as validate_section
from backend.llm import client, prompts, sdk
from backend.numbers import invented
from backend.orchestrator.context import tag, user_message
from backend.paths import REPO_ROOT
from backend.schemas import (
    GateGrade,
    Paragraph,
    ReadmeReview,
    ReviewNote,
    Section,
    Slide,
    SlideDraft,
    Status,
)
from backend.workspace import git, sandbox

CALIBRATION = REPO_ROOT / "calibration"
Scores = dict[str, float]

# ---- gate: the grader agrees with expected statuses


class GateStep(BaseModel):
    title: str
    component: str
    goal: str
    concepts: list[str]


class GradedAnswer(BaseModel):
    style: str
    text: str
    expected: list[Status]


class GateSet(BaseModel):
    step: GateStep
    build_summary: str
    question: str
    rubric: list[str]
    answers: list[GradedAnswer]


def gate_sets() -> dict[str, GateSet]:
    return {
        p.stem: GateSet.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
        for p in sorted((CALIBRATION / "gate").glob("*.yaml"))
    }


async def gate() -> Scores:
    from backend.orchestrator.runner import grader_message

    async def one(name: str, s: GateSet, a: GradedAnswer) -> Scores:
        step = tag(
            "step",
            f"Title: {s.step.title}\nComponent: {s.step.component}\nGoal: {s.step.goal}\n"
            f"Concepts: {', '.join(s.step.concepts)}",
        )
        msg = grader_message(s.rubric, step, s.build_summary, [a.text], [s.question])
        result = await client.structured("grader", msg, GateGrade)
        got = rubric.merge([Item(t) for t in s.rubric], result, [a.text])
        return {
            f"gate/{name}/{a.style}/{i}": float(g.status == e)
            for i, (g, e) in enumerate(zip(got, a.expected, strict=True))
        }

    limit = asyncio.Semaphore(4)

    async def limited(name: str, s: GateSet, a: GradedAnswer) -> Scores:
        async with limit:
            return await one(name, s, a)

    parts = await asyncio.gather(
        *(limited(n, s, a) for n, s in gate_sets().items() for a in s.answers)
    )
    return {k: v for part in parts for k, v in part.items()}


# ---- slides: no claim the step bundle does not support


class SlideBundle(BaseModel):
    step: str
    build_summary: str
    build_note: str
    review_note: str
    code_files: str
    gate: str
    forbidden: list[str]


def slide_bundles() -> dict[str, SlideBundle]:
    return {
        p.stem: SlideBundle.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
        for p in sorted((CALIBRATION / "slides").glob("*.yaml"))
    }


def slide_claims(slide: Slide) -> str:
    """Every sentence the slide states, without hint counts and code line numbers."""
    v = slide.visual
    parts = [slide.title, slide.kicker, slide.what, slide.notes, *slide.failure_and_scale]
    parts += [f"{d.choice} {d.tradeoff}" for d in slide.decisions]
    parts += [s.question for s in slide.struggled]
    if v.kind == "architecture":
        parts += [n.label for n in v.spec.nodes] + [e.label for e in v.spec.edges]
    elif v.kind == "flow":
        parts += v.spec.steps
    elif v.kind == "table":
        parts += v.spec.columns + [c for row in v.spec.rows for c in row]
    elif v.kind == "chart":
        parts += [
            v.spec.x_label,
            v.spec.y_label,
            *(str(x) for s in v.spec.series for x in [*s.x, *s.y]),
        ]
    return "\n".join(parts)


def slide_problems(bundle: SlideBundle, slide: Slide) -> list[str]:
    source = "\n".join(bundle.model_dump(exclude={"forbidden"}).values())
    said = slide_claims(slide)
    found = [f"number {n} is not in the bundle" for n in invented(said, source)]
    found += [f"unsupported claim '{t}'" for t in bundle.forbidden if t.lower() in said.lower()]
    if slide.visual.kind == "code" and slide.visual.spec.path not in bundle.code_files:
        found.append(f"code visual points at {slide.visual.spec.path}")
    return found


async def slides() -> Scores:
    from backend.orchestrator.slides import step_message

    async def one(bundle: SlideBundle) -> Slide:
        message = step_message(
            tag("step", bundle.step), bundle.build_summary, bundle.build_note,
            bundle.review_note, bundle.code_files, bundle.gate,
        )  # fmt: skip
        draft = await client.structured("slide_writer", user_message(message), SlideDraft)
        return draft.to_slide()

    bundles = slide_bundles()
    made = await asyncio.gather(*(one(b) for b in bundles.values()))
    return {
        f"slides/{name}": float(not slide_problems(b, s))
        for (name, b), s in zip(bundles.items(), made, strict=True)
    }


# ---- readme: every planted mismatch is flagged, nothing is rewritten


class Planted(BaseModel):
    line: int
    shows: list[str]


class ReadmeCase(BaseModel):
    project: str
    readme: str
    planted: list[Planted]


def readme_cases() -> dict[str, ReadmeCase]:
    return {
        p.stem: ReadmeCase.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
        for p in sorted((CALIBRATION / "readme").glob("*.yaml"))
    }


def rewrites(review: ReadmeReview) -> bool:
    return any("\n#" in n.note or "```" in n.note or len(n.note.split()) > 80 for n in review.notes)


async def readme() -> Scores:
    scores: Scores = {}
    for name, case in readme_cases().items():
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(case.readme.splitlines(), 1))
        review = await client.structured(
            "readme_coach",
            user_message(
                tag("mode", "review"), tag("project", case.project), tag("readme", numbered)
            ),
            ReadmeReview,
        )
        for p in case.planted:
            flagged = any(
                n.kind == "does_not_match"
                and abs(n.line - p.line) <= 1
                and any(w.lower() in n.project_shows.lower() for w in p.shows)
                for n in review.notes
            )
            scores[f"readme/{name}/line{p.line}"] = float(flagged)
        scores[f"readme/{name}/no_rewrite"] = float(not rewrites(review))
    return scores


# ---- lessons: the deterministic validator


def lessons() -> Scores:
    data = yaml.safe_load((CALIBRATION / "lessons" / "planted.yaml").read_text(encoding="utf-8"))
    retrieved = {
        pid: Passage(pid, p["text"], p["kind"], "t", 1.0) for pid, p in data["passages"].items()
    }
    scores = {}
    for case in data["sections"]:
        section = Section(
            kind="start_here", paragraphs=[Paragraph(**p) for p in case["paragraphs"]],
            visual_json="", code="", questions=[],
        )  # fmt: skip
        errors = validate_section(section, retrieved, data["terms"])
        right = len(errors) == len(case["expect"]) and all(
            e in err for err, e in zip(errors, case["expect"], strict=False)
        )
        scores[f"lessons/{case['name']}"] = float(right)
    return scores


# ---- reviewer: planted unreachable branches cut, boundary checks kept


class Marker(BaseModel):
    file: str
    marker: str


class ReviewerStep(BaseModel):
    title: str
    goal: str
    files: list[str]
    acceptance: list[str]


class ReviewerCase(BaseModel):
    step: ReviewerStep
    build_note: str
    unreachable: list[Marker]
    boundary: list[Marker]
    files: list[Path] = []


def reviewer_cases() -> dict[str, ReviewerCase]:
    cases = {}
    for folder in sorted(p for p in (CALIBRATION / "reviewer").iterdir() if p.is_dir()):
        case = ReviewerCase.model_validate(
            yaml.safe_load((folder / "case.yaml").read_text(encoding="utf-8"))
        )
        case.files = sorted(folder.glob("*.py"))
        cases[folder.name] = case
    return cases


async def review_case(box: int, name: str, case: ReviewerCase) -> tuple[ReviewNote, dict[str, str]]:
    """Run the real reviewer on a planted repo in sandbox `box`; return its note and the files."""
    repo = git.workspace_path(box)
    if repo.exists():
        shutil.rmtree(repo)  # a scratch copy from an earlier calibration run, never a project
    repo = git.init(box, name)
    base = git.head(repo)
    for path in case.files:
        shutil.copy(path, repo / path.name)
    await sandbox.run(box, "pip install -q pytest", allow_install=True)
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
        project_id=None, step_id=None, allow_install=False, resume=go, box=box,
    )  # fmt: skip
    after = {
        p.name: (repo / p.name).read_text(encoding="utf-8")
        for p in case.files
        if (repo / p.name).exists()
    }
    return note, after


REVIEWER_BOXES = 900_000  # scratch project ids for calibration repos, far above real projects


async def reviewer() -> Scores:
    cases = reviewer_cases()
    results = await asyncio.gather(
        *(review_case(REVIEWER_BOXES + i, n, c) for i, (n, c) in enumerate(cases.items()))
    )
    scores = {}
    for (name, case), (note, after) in zip(cases.items(), results, strict=True):
        cut = [m.marker not in after.get(m.file, "") for m in case.unreachable]
        kept = [m.marker in after.get(m.file, "") for m in case.boundary]
        scores[f"reviewer/{name}"] = float(all(cut) and all(kept) and note.status == "pass")
    return scores


# ---- which sets a change touches, and running them against an overlay

SETS: dict[str, Callable[[], Awaitable[Scores]]] = {
    "gate": gate, "slides": slides, "readme": readme, "reviewer": reviewer,
}  # fmt: skip
RELEVANT = {
    "prompts/grader.md": "gate", "prompts/interviewer.md": "gate",
    "prompts/slide_writer.md": "slides", "templates/slides/**": "slides",
    "prompts/readme_coach.md": "readme", "templates/readme/**": "readme",
    "prompts/reviewer.md": "reviewer",
    "backend/lessons/**": "lessons", "prompts/lesson_builder.md": "lessons",
    "content/quizzes/**": "lessons",
}  # fmt: skip


def relevant(paths: list[str]) -> set[str]:
    return {s for p in paths for pattern, s in RELEVANT.items() if fnmatch(p, pattern)}


def overlay(files: dict[str, str | None]) -> Path:
    """A copy of the data folders with `files` applied (None removes one)."""
    folder = Path(tempfile.mkdtemp(prefix="vcpg-overlay-"))
    for name in ("prompts", "templates", "content"):
        if (REPO_ROOT / name).exists():
            shutil.copytree(REPO_ROOT / name, folder / name)
    for path, content in files.items():
        target = folder / path
        if content is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    return folder


async def score(names: set[str], files: dict[str, str | None]) -> Scores:
    """Run the named sets with `files` overlaid on the prompts and templates."""
    folder = overlay(files)
    token = prompts.root.set(folder)
    try:
        scores: Scores = {}
        for name in sorted(names):
            scores |= lessons() if name == "lessons" else await SETS[name]()
        return scores
    finally:
        prompts.root.reset(token)
        shutil.rmtree(folder, ignore_errors=True)
