"""Gate state is computed here from grader output; the grader never decides pass or fail."""

import re
from dataclasses import dataclass, replace

from backend.schemas import GateGrade, Status

RANK: dict[Status, int] = {"missing": 0, "partial": 1, "covered": 2}
MAX_HINT_LEVEL = 3  # nudge, narrower question, pointer to the code
RETEACH_AFTER = 3  # answers in a row that cover nothing new
SMART_QUOTES = str.maketrans({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'})


@dataclass(frozen=True)
class Item:
    text: str
    status: Status = "missing"
    evidence: str | None = None


def _normalise(text: str) -> str:
    text = text.lower().translate(SMART_QUOTES)
    return re.sub(r"\s+", " ", text).strip(" \"'.,;:!?")


def quote_found(quote: str, answers: list[str]) -> bool:
    needle = _normalise(quote)
    return bool(needle) and any(needle in _normalise(a) for a in answers)


def merge(items: list[Item], grade: GateGrade, answers: list[str]) -> list[Item]:
    """Apply a grade: unverifiable evidence counts as missing, and no status ever goes down."""
    merged = list(items)
    for g in grade.items:
        if not 0 <= g.item_index < len(items):
            continue
        status: Status = g.status
        if status != "missing" and not (g.evidence and quote_found(g.evidence, answers)):
            status = "missing"
        current = merged[g.item_index]
        if RANK[status] > RANK[current.status]:
            merged[g.item_index] = replace(current, status=status, evidence=g.evidence)
    return merged


def passed(items: list[Item]) -> bool:
    return all(i.status == "covered" for i in items)


def improved(before: list[Item], after: list[Item]) -> bool:
    return any(RANK[a.status] > RANK[b.status] for b, a in zip(before, after, strict=True))


def needs_reteach(improvements_since_reteach: list[bool]) -> bool:
    recent = improvements_since_reteach[-RETEACH_AFTER:]
    return len(recent) == RETEACH_AFTER and not any(recent)


def hint_level(hints_since_progress: int) -> int:
    return min(hints_since_progress + 1, MAX_HINT_LEVEL)


def progress(items: list[Item]) -> dict[str, int]:
    """The only view of the rubric the user ever gets: counts."""
    return {"covered": sum(i.status == "covered" for i in items), "total": len(items)}
