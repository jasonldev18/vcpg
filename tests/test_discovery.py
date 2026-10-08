"""Ideas, lesson paths with validated sections, lesson questions, and sources."""

import json
import socket
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.lessons import builder, sources
from tests.conftest import FakeLLM

COSINE = (
    "Cosine similarity measures the angle between two vectors and ignores their length. "
    "In recommender systems it compares users by the direction of their rating vectors. " * 3
)

pytestmark = pytest.mark.network  # local sockets or the embedding model download


def card(name: str, concepts: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "line": f"{name} in one line",
        "pitch": "A pitch.",
        "difficulty": "medium",
        "step_count": 5,
        "thumbnail": {"template": "ranked", "data_json": json.dumps({"query": "q", "items": []})},
        "concepts": [{"name": c, "familiarity": "new"} for c in concepts],
        "architecture": ["Data", "Model", "API"],
        "questions": ["Why cosine?"],
    }


def paragraph(text: str, *ids: str) -> dict[str, Any]:
    return {"text": text, "citations": list(ids)}


def section(kind: str, *paragraphs: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "paragraphs": list(paragraphs),
        "visual_json": "",
        "code": "",
        "questions": [],
    }


@pytest.fixture
def offline_seeds(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    fetched: list[str] = []

    def fetch(url: str) -> str:
        fetched.append(url)
        return COSINE

    monkeypatch.setattr(sources, "fetch", fetch)
    return fetched


def test_ideas_get_familiarity_from_history_and_build_a_plan(
    api: TestClient, fake_llm: FakeLLM
) -> None:
    with db.session() as conn:
        pid = conn.execute(
            "INSERT INTO projects (name, brief, start_path, status)"
            " VALUES ('old', 'b', 'plan', 'done')"
        ).lastrowid
        conn.execute(
            "INSERT INTO steps (project_id, position, title, component, goal, concepts, state)"
            " VALUES (?, 0, 't', 'backend', 'g', ?, 'slide_done')",
            (pid, json.dumps(["Cosine similarity"])),
        )
    cards = [card(f"Idea {i}", ["cosine similarity", "embeddings", "chunking"]) for i in range(4)]
    fake_llm.reply("idea_generator", json.dumps({"cards": cards}))
    view = api.post("/api/ideas", json={"topic": "RAG and vectors", "use": "study notes"}).json()
    assert len(view["cards"]) == 4
    assert [c["familiarity"] for c in view["cards"][0]["concepts"]] == ["used", "new", "new"]
    sent = fake_llm.requests_for("idea_generator")[0][0]["content"]
    assert "<topic>\nRAG and vectors\n</topic>" in sent and "cosine similarity" in sent

    fake_llm.reply_fixture("planner", "plan_recommender.json")
    project = api.post(f"/api/ideas/{view['id']}/build", json={"card": 2}).json()
    assert project["brief"].startswith("Idea 2: Idea 2 in one line")
    with db.session() as conn:
        start = conn.execute(
            "SELECT start_path FROM projects WHERE id = ?", (project["id"],)
        ).fetchone()[0]
    assert start == "idea"
    assert api.post(f"/api/ideas/{view['id']}/build", json={"card": 9}).status_code == 404


def test_teach_me_first_builds_a_path_for_new_concepts_and_remembers_the_card(
    api: TestClient, fake_llm: FakeLLM, offline_seeds: list[str]
) -> None:
    fake_llm.reply(
        "idea_generator",
        json.dumps({"cards": [card("A", ["cosine similarity", "embedding", "chunking"])] * 4}),
    )
    idea = api.post("/api/ideas", json={"topic": "vectors"}).json()
    outline = [
        {"title": f"L{i}", "goal": "g", "key_terms": ["cosine similarity"]} for i in range(4)
    ]
    fake_llm.reply("lesson_builder", json.dumps({"lessons": outline}))
    path = api.post(f"/api/ideas/{idea['id']}/teach", json={"card": 1}).json()
    assert (path["return_idea_id"], path["return_card"]) == (idea["id"], 1)
    assert path["concept"] == "cosine similarity, embedding, chunking"
    assert offline_seeds  # nothing was stored, so the seeded docs for the topic were fetched
    assert "[1:0]" in fake_llm.requests_for("lesson_builder")[0][0]["content"]


def test_lesson_sections_are_validated_regenerated_then_dropped(
    api: TestClient, fake_llm: FakeLLM, offline_seeds: list[str]
) -> None:
    sources.add("Cosine notes", COSINE, "notes.md", "trusted", "user")
    sources.add(
        "Forum",
        "cosine is great for everything honestly, I use it daily",
        "forum",
        "community",
        "user",
    )
    outline = [
        {"title": f"L{i}", "goal": "cosine similarity", "key_terms": ["cosine similarity"]}
        for i in range(4)
    ]
    fake_llm.reply("lesson_builder", json.dumps({"lessons": outline}))
    lesson_id = api.post("/api/lessons", json={"concept": "cosine similarity"}).json()["id"]

    good = paragraph("Cosine similarity compares the angle between vectors.", "1:0")
    lesson = {
        "title": "Cosine",
        "by_the_end": ["compare users"],
        "sections": [
            section("start_here", good),
            section("see_it", paragraph("Cosine similarity ignores length.")),  # no citation
            section("recap", paragraph("Cosine similarity is popular.", "2:0")),  # community
        ],
        "community": [
            {"text": "People use it daily.", "source_id": "2:0"},
            {"text": "x", "source_id": "1:0"},
        ],
    }
    fake_llm.reply("lesson_builder", json.dumps(lesson))
    fake_llm.reply("lesson_builder", json.dumps(section("see_it", good)))  # fixed on the first try
    bad = section("recap", paragraph("Cosine similarity is popular.", "9:9"))
    fake_llm.reply("lesson_builder", json.dumps(bad))
    fake_llm.reply("lesson_builder", json.dumps(bad))
    view = api.post(f"/api/lessons/{lesson_id}/build/0").json()

    built = view["lessons"][0]
    assert [s["kind"] for s in built["content"]["sections"]] == ["start_here", "see_it"]
    assert built["dropped"] == ["recap"]
    assert [n["source_id"] for n in built["content"]["community"]] == ["2:0"]
    assert built["passages"]["1:0"]["title"] == "Cosine notes"
    retry = fake_llm.requests_for("lesson_builder")[2][0]["content"]
    assert "<mode>\nsection\n</mode>" in retry and "see_it paragraph 1 has no citation" in retry
    assert view["status"] == "active"
    api.post(f"/api/lessons/{lesson_id}/build/0")
    assert len(fake_llm.requests_for("lesson_builder")) == 5  # a built lesson is kept


def test_short_answers_are_graded_against_the_mini_rubric(
    api: TestClient, fake_llm: FakeLLM, offline_seeds: list[str]
) -> None:
    outline = [{"title": f"L{i}", "goal": "g", "key_terms": []} for i in range(4)]
    fake_llm.reply("lesson_builder", json.dumps({"lessons": outline}))
    lesson_id = api.post("/api/lessons", json={"concept": "cosine similarity"}).json()["id"]
    question = {
        "type": "short", "prompt": "Why cosine?", "options": [], "answer": "direction",
        "rubric": ["mentions direction", "mentions length"], "tests": "",
    }  # fmt: skip
    turn = {**section("your_turn"), "questions": [question]}
    lesson = {"title": "t", "by_the_end": [], "sections": [turn], "community": []}
    fake_llm.reply("lesson_builder", json.dumps(lesson))
    api.post(f"/api/lessons/{lesson_id}/build/0")
    grade = {
        "items": [
            {"item_index": 0, "status": "covered", "evidence": "only the direction", "reason": "r"},
            {"item_index": 1, "status": "covered", "evidence": "not in the answer", "reason": "r"},
        ],
        "gap": "mention length",
    }
    fake_llm.reply("grader", json.dumps(grade))
    body = {
        "lesson": 0,
        "section": "your_turn",
        "question": 0,
        "answer": "It uses only the direction.",
    }
    result = api.post(f"/api/lessons/{lesson_id}/answer", json=body).json()
    assert result == {"covered": 1, "total": 2, "feedback": "mention length"}
    body["question"] = 5
    assert api.post(f"/api/lessons/{lesson_id}/answer", json=body).status_code == 404


def _online() -> bool:
    try:
        socket.create_connection(("pypi.org", 443), 3).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _online(), reason="installs pytest into the lesson sandbox")
async def test_code_answers_run_their_tests_in_the_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.workspace import sandbox

    monkeypatch.setattr(sandbox, "docker_available", lambda: False)
    tests = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    ok = await builder._run_code(7, "def add(a, b):\n    return a + b\n", tests)
    wrong = await builder._run_code(7, "def add(a, b):\n    return a - b\n", tests)
    assert ok["passed"] is True and wrong["passed"] is False and "assert" in wrong["output"]


def test_sources_from_upload_and_url(api: TestClient, offline_seeds: list[str]) -> None:
    listed = api.post(
        "/api/sources/upload?filename=notes.md&kind=community",
        content=COSINE.encode(),
        headers={"Content-Type": "application/octet-stream"},
    ).json()
    assert listed[0]["title"] == "notes.md" and listed[0]["kind"] == "community"
    assert api.post("/api/sources/upload?filename=x.exe", content=b"MZ").status_code == 409
    listed = api.post("/api/sources/url", json={"url": "https://example.com/doc"}).json()
    assert listed[-1]["url_or_path"] == "https://example.com/doc" and listed[-1]["passages"] == 1
