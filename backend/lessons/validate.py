"""The grounding rule (SPEC 9.2), checked in code: no LLM decides whether a lesson is cited."""

import re

from backend.lessons.retrieve import Passage
from backend.schemas import Section


def _mentions(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term.lower())}", text.lower()) is not None


def check(section: Section, retrieved: dict[str, Passage], terms: list[str]) -> list[str]:
    """Why this section breaks the rule; empty when it may be shown."""
    errors = []
    for n, paragraph in enumerate(section.paragraphs, 1):
        where = f"{section.kind} paragraph {n}"
        if not paragraph.citations:
            errors.append(f"{where} has no citation.")
            continue
        cited = []
        for passage_id in paragraph.citations:
            passage = retrieved.get(passage_id)
            if passage is None:
                errors.append(
                    f"{where} cites {passage_id}, which was not retrieved for this lesson."
                )
            elif passage.kind == "community":
                errors.append(
                    f"{where} cites community source {passage_id}; community never supports claims."
                )
            else:
                cited.append(passage.text)
        for term in terms:
            if (
                _mentions(paragraph.text, term)
                and cited
                and not any(_mentions(t, term) for t in cited)
            ):
                errors.append(f"{where} uses '{term}', which none of its cited passages mention.")
    return errors
