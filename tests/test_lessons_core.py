"""Passage splitting, HTML text, retrieval and the deterministic citation validator."""

import pytest

from backend.errors import Conflict
from backend.lessons import retrieve, sources, validate
from backend.lessons.retrieve import Passage
from backend.schemas import Paragraph, Section

COSINE = "Cosine similarity measures the angle between two vectors, ignoring their length."
KNN = "k-nearest neighbours predicts from the k closest training examples to a query point."


def section(*paragraphs: tuple[str, list[str]]) -> Section:
    return Section(
        kind="start_here",
        paragraphs=[Paragraph(text=t, citations=c) for t, c in paragraphs],
        visual_json="",
        code="",
        questions=[],
    )


RETRIEVED = {
    "1:0": Passage("1:0", COSINE, "trusted", "Notes", 0.9),
    "1:1": Passage("1:1", KNN, "trusted", "Notes", 0.8),
    "2:0": Passage("2:0", "I just use cosine for everything lol", "community", "Forum", 0.7),
}
TERMS = ["cosine similarity", "k-nearest neighbours", "embedding"]


def test_a_cited_paragraph_passes() -> None:
    ok = section(("Cosine similarity looks at the angle between vectors.", ["1:0"]))
    assert validate.check(ok, RETRIEVED, TERMS) == []


@pytest.mark.parametrize(
    ("paragraph", "citations", "error"),
    [
        ("Cosine similarity looks at angles.", [], "no citation"),
        ("Cosine similarity looks at angles.", ["9:9"], "was not retrieved"),
        ("Cosine similarity looks at angles.", ["2:0"], "community"),
        ("An embedding turns text into numbers.", ["1:0"], "'embedding'"),
    ],
)
def test_the_validator_rejects(paragraph: str, citations: list[str], error: str) -> None:
    [found] = validate.check(section((paragraph, citations)), RETRIEVED, TERMS)
    assert error in found


def test_split_makes_200_to_400_word_passages_at_boundaries() -> None:
    para = " ".join(["word"] * 120)
    text = "# Intro\n\n" + "\n\n".join([para] * 7)
    passages = sources.split(text)
    sizes = [len(p.split()) for p in passages]
    assert all(200 <= s <= 400 for s in sizes[:-1]) and sum(sizes) == 842  # 840 + '# Intro'
    assert sources.split(" ".join(["x"] * 900))[0].count("x") == 400


def test_html_text_prefers_the_main_content() -> None:
    html = (
        "<html><nav>Home Docs</nav><script>x()</script><main><h1>Cosine</h1><p>"
        + "angle " * 120
        + "</p></main><footer>(c)</footer></html>"
    )
    text = sources.html_to_text(html)
    assert text.startswith("# Cosine") and "Home" not in text and "x()" not in text


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8000/api/session", "file:///etc/passwd", "http://localhost/"]
)
def test_fetch_refuses_local_and_non_web_urls(url: str) -> None:
    with pytest.raises(Conflict):
        sources.fetch(url)


def test_retrieval_ranks_by_meaning_and_keeps_kinds_apart() -> None:
    sources.add("Cosine notes", COSINE, "cosine.md", "trusted", "user")
    sources.add("KNN notes", KNN, "knn.md", "trusted", "user")
    sources.add(
        "Forum",
        "Honestly cosine is my favourite, it just works for me.",
        "forum",
        "community",
        "user",
    )
    [best, _] = retrieve.search("how does the angle between vectors work", 2, "trusted")
    assert best.text == COSINE and best.id == "1:0" and best.kind == "trusted"
    assert [p.kind for p in retrieve.search("cosine", 5, "community")] == ["community"]
