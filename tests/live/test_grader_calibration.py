"""Live: the real grader, through the real gate pipeline, must agree with calibration/gate/."""

import asyncio

import pytest

from backend import secrets
from backend.gate import rubric
from backend.gate.rubric import Item
from backend.llm import client
from backend.orchestrator.context import tag
from backend.orchestrator.runner import grader_message
from backend.schemas import GateGrade, Status
from tests.calibration import GateSet, GradedAnswer, gate_sets

pytestmark = pytest.mark.live
REQUIRED_AGREEMENT = 0.9


async def grade(gate: GateSet, answer: GradedAnswer) -> list[Status]:
    step = tag(
        "step",
        f"Title: {gate.step.title}\nComponent: {gate.step.component}\nGoal: {gate.step.goal}\n"
        f"Concepts: {', '.join(gate.step.concepts)}",
    )
    msg = grader_message(gate.rubric, step, gate.build_summary, [answer.text], [gate.question])
    result = await client.structured("grader", msg, GateGrade)
    items = rubric.merge([Item(text) for text in gate.rubric], result, [answer.text])
    return [i.status for i in items]


async def test_grader_agrees_with_calibration_set() -> None:
    if not secrets.get("anthropic"):
        pytest.fail("Save an Anthropic key in Core access before running `make live`.")
    cases = [(name, gate, a) for name, gate in gate_sets().items() for a in gate.answers]
    limit = asyncio.Semaphore(4)

    async def run(gate: GateSet, answer: GradedAnswer) -> list[Status]:
        async with limit:
            return await grade(gate, answer)

    results = await asyncio.gather(*(run(gate, a) for _, gate, a in cases))

    total = agreed = 0
    report = []
    for (name, _, answer), got in zip(cases, results, strict=True):
        hits = sum(g == e for g, e in zip(got, answer.expected, strict=True))
        total, agreed = total + len(got), agreed + hits
        mark = "ok " if hits == len(got) else "MISS"
        report.append(f"{mark} {name}/{answer.style}: expected {answer.expected}, got {got}")
    agreement = agreed / total
    print("\n".join(report) + f"\nagreement: {agreed}/{total} = {agreement:.0%}")
    assert agreement >= REQUIRED_AGREEMENT, "\n".join(report)
