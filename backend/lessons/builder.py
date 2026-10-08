"""Lesson paths: outline, then each lesson on demand, validated in code (SPEC section 9)."""

import json
import re
import sqlite3
from typing import Any

import yaml

from backend import db
from backend.errors import Conflict, NotFound
from backend.gate import rubric
from backend.gate.rubric import Item
from backend.lessons import retrieve, sources, validate
from backend.lessons.retrieve import Passage
from backend.llm import client
from backend.orchestrator.context import history, tag, user_message
from backend.paths import REPO_ROOT
from backend.schemas import GateGrade, Lesson, LessonPath, Section
from backend.workspace import git, sandbox

RELEVANT = 0.3  # below this cosine score, retrieved passages are off topic
REGENERATE = 2  # tries per rejected section before it is dropped
LESSON_BOX = 0  # sandbox id for running lesson code answers; no project uses 0
DROPPED_NOTE = "This section was left out: the topic needs a source that supports it."


def _seeds_for(concept: str) -> list[dict[str, Any]]:
    seeds = yaml.safe_load((REPO_ROOT / "content" / "sources.yaml").read_text(encoding="utf-8"))
    words = set(re.findall(r"[a-z0-9-]+", concept.lower()))
    return [s for s in seeds if words & set(s["topics"])]


def ensure_sources(concept: str) -> None:
    """Fetch the seeded official docs for a topic when nothing on it is stored yet."""
    best = retrieve.search(concept, 1, "trusted")
    if best and best[0].score >= RELEVANT:
        return
    known = sources.known_urls()
    for seed in _seeds_for(concept):
        if seed["url"] not in known:
            sources.add(seed["title"], sources.fetch(seed["url"]), seed["url"], "trusted", "seed")


def _row(conn: sqlite3.Connection, lesson_id: int) -> sqlite3.Row:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM lessons WHERE id = ?", (lesson_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"Lesson path {lesson_id} does not exist.")
    return row


def _passages_block(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{p.id}] ({p.title})\n{p.text}" for p in passages) or "(none found)"


async def create_path(
    concept: str, return_idea: int | None = None, return_card: int | None = None
) -> int:
    ensure_sources(concept)
    passages = [p for p in retrieve.search(concept, 6, "trusted") if p.score >= RELEVANT]
    with db.session() as conn:
        learner = history(conn, exclude_project=0)
    message = user_message(
        tag("mode", "path"),
        tag("concept", concept),
        tag("learner", learner),
        tag("passages", _passages_block(passages)),
    )
    path = await client.structured("lesson_builder", message, LessonPath)
    data = {
        "concept": concept,
        "lessons": [{**o.model_dump(), "content": None, "dropped": []} for o in path.lessons],
    }
    with db.session() as conn:
        lesson_id = conn.execute(
            "INSERT INTO lessons (concept, path_json, status, return_idea_id, return_card)"
            " VALUES (?, ?, 'active', ?, ?)",
            (concept, json.dumps(data), return_idea, return_card),
        ).lastrowid
    assert lesson_id is not None
    return lesson_id


async def _fix_section(
    lesson: Lesson, section: Section, errors: list[str], context: list[str]
) -> Section:
    message = user_message(
        tag("mode", "section"),
        *context,
        tag("lesson", lesson.model_dump_json()),
        tag("errors", "\n".join(errors)),
    )
    fixed = await client.structured("lesson_builder", message, Section)
    return fixed.model_copy(update={"kind": section.kind})


async def build_lesson(lesson_id: int, index: int) -> None:
    """Write one lesson; sections that break the grounding rule are regenerated, then dropped."""
    with db.session() as conn:
        row = _row(conn, lesson_id)
        learner = history(conn, exclude_project=0)
    data = json.loads(row["path_json"])
    if not 0 <= index < len(data["lessons"]):
        raise NotFound("That lesson is not in this path.")
    outline = data["lessons"][index]
    if outline["content"]:
        return
    query = f"{outline['title']}. {outline['goal']} {' '.join(outline['key_terms'])}"
    ensure_sources(f"{data['concept']} {query}")
    trusted = retrieve.search(query, 8, "trusted")
    community = retrieve.search(query, 3, "community")
    retrieved = {p.id: p for p in [*trusted, *community]}
    context = [
        tag("concept", data["concept"]),
        tag("learner", learner),
        tag("outline", json.dumps({k: outline[k] for k in ("title", "goal", "key_terms")})),
        tag("passages", _passages_block(trusted)),
        tag(
            "community",
            "\n\n".join(f"[{p.id}] ({p.title}) {p.text}" for p in community) or "(none)",
        ),
    ]
    lesson = await client.structured(
        "lesson_builder", user_message(tag("mode", "lesson"), *context), Lesson
    )
    terms = sorted({t for o in data["lessons"] for t in o["key_terms"]})
    kept, dropped = [], []
    for section in lesson.sections:
        errors = validate.check(section, retrieved, terms)
        for _ in range(REGENERATE):
            if not errors:
                break
            section = await _fix_section(lesson, section, errors, context)
            errors = validate.check(section, retrieved, terms)
        (dropped.append(section.kind) if errors else kept.append(section))
    community_ids = {p.id for p in community}
    notes = [n for n in lesson.community if n.source_id in community_ids]
    final = lesson.model_copy(update={"sections": kept, "community": notes})
    outline["content"] = final.model_dump()
    outline["dropped"] = dropped
    outline["passages"] = {p.id: {"title": p.title, "text": p.text} for p in trusted}
    with db.session() as conn:
        done = all(o["content"] for o in data["lessons"])
        conn.execute(
            "UPDATE lessons SET path_json = ?, status = ? WHERE id = ?",
            (json.dumps(data), "done" if done else "active", lesson_id),
        )


def _question(lesson_id: int, index: int, kind: str, number: int) -> dict[str, Any]:
    with db.session() as conn:
        data = json.loads(_row(conn, lesson_id)["path_json"])
    try:
        content = data["lessons"][index]["content"]
        section = next(s for s in content["sections"] if s["kind"] == kind)
        return dict(section["questions"][number])
    except (IndexError, KeyError, StopIteration, TypeError):
        raise NotFound("That question is not in this lesson.") from None


async def answer(lesson_id: int, index: int, kind: str, number: int, text: str) -> dict[str, Any]:
    """Short answers are graded against their mini rubric; code answers run their tests."""
    question = _question(lesson_id, index, kind, number)
    if question["type"] == "short":
        message = user_message(
            tag("rubric", "\n".join(f"{i}. {r}" for i, r in enumerate(question["rubric"]))),
            tag("step", f"Lesson question: {question['prompt']}"),
            tag("build_summary", f"Model answer: {question['answer']}"),
            tag("learner_answers", f"[1] {text}"),
            tag("interviewer_questions", question["prompt"]),
        )
        grade = await client.structured("grader", message, GateGrade)
        items = rubric.merge([Item(r) for r in question["rubric"]], grade, [text])
        return {**rubric.progress(items), "feedback": grade.gap}
    if question["type"] == "code":
        return await _run_code(lesson_id, text, question["tests"])
    raise Conflict("Multiple choice and true/false answers are checked in the page.")


async def _run_code(lesson_id: int, code: str, tests: str) -> dict[str, Any]:
    folder = git.workspace_path(LESSON_BOX) / f"lesson_{lesson_id}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "solution.py").write_text(code, encoding="utf-8")
    (folder / "test_solution.py").write_text(tests, encoding="utf-8")
    if not sandbox.venv_has(LESSON_BOX, "pytest"):
        await sandbox.run(LESSON_BOX, "pip install -q pytest", allow_install=True)
    result = await sandbox.run(
        LESSON_BOX, f"python -m pytest -q -p no:cacheprovider lesson_{lesson_id}", timeout=60
    )
    return {"passed": result.exit_code == 0, "output": result.output[-4000:]}


def view(lesson_id: int) -> dict[str, Any]:
    with db.session() as conn:
        row = _row(conn, lesson_id)
    data = json.loads(row["path_json"])
    return {
        "id": row["id"],
        "concept": row["concept"],
        "status": row["status"],
        "return_idea_id": row["return_idea_id"],
        "return_card": row["return_card"],
        "lessons": data["lessons"],
        "dropped_note": DROPPED_NOTE,
    }


def studied_concepts() -> set[str]:
    """Concepts the learner has met in lessons: 'know the basics' on idea cards."""
    with db.session() as conn:
        rows = conn.execute("SELECT concept, path_json FROM lessons").fetchall()
    found = set()
    for r in rows:
        found.add(r["concept"].lower())
        for o in json.loads(r["path_json"])["lessons"]:
            if o["content"]:
                found |= {t.lower() for t in o["key_terms"]}
    return found
