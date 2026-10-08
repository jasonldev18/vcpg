"""Top-k passages for a query: brute-force cosine over stored embeddings (small enough)."""

from dataclasses import dataclass

import numpy as np

from backend import db
from backend.lessons.sources import Kind, embed


@dataclass(frozen=True)
class Passage:
    id: str  # "<source_id>:<position>", stable across runs
    text: str
    kind: Kind
    title: str
    score: float


def search(query: str, k: int, kind: Kind) -> list[Passage]:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT p.source_id, p.position, p.text, p.embedding, s.title FROM passages p"
            " JOIN sources s ON s.id = p.source_id WHERE s.kind = ?",
            (kind,),
        ).fetchall()
    if not rows:
        return []
    [q] = embed([query])
    matrix = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    scores = matrix @ q / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(q) + 1e-9)
    best = np.argsort(-scores)[:k]
    return [
        Passage(
            f"{rows[i]['source_id']}:{rows[i]['position']}",
            rows[i]["text"],
            kind,
            rows[i]["title"],
            float(scores[i]),
        )
        for i in best
    ]
