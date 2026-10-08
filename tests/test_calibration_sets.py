from tests.calibration import STYLES, gate_sets, reviewer_cases


def test_gate_sets_cover_every_answer_style_with_a_status_per_item() -> None:
    sets = gate_sets()
    assert len(sets) >= 3
    for name, gate in sets.items():
        assert 3 <= len(gate.rubric) <= 5, name
        assert {a.style for a in gate.answers} == STYLES, name
        for answer in gate.answers:
            assert len(answer.expected) == len(gate.rubric), f"{name}/{answer.style}"


def test_strong_answers_cover_everything_and_off_topic_answers_nothing() -> None:
    for gate in gate_sets().values():
        by_style = {a.style: a.expected for a in gate.answers}
        assert set(by_style["strong"]) == {"covered"}
        assert set(by_style["off_topic"]) == {"missing"}


def test_reviewer_cases_have_markers_in_their_files() -> None:
    cases = reviewer_cases()
    assert len(cases) >= 3
    for name, case in cases.items():
        sources = {p.name: p.read_text(encoding="utf-8") for p in case.files}
        assert case.unreachable and case.boundary, name
        for m in [*case.unreachable, *case.boundary]:
            assert sources[m.file].count(m.marker) == 1, f"{name}: {m.marker}"


def test_lesson_validator_calibration() -> None:
    from backend.audit import testsets

    scores = testsets.lessons()
    assert scores and all(scores.values()), scores


def test_changes_map_to_their_calibration_sets() -> None:
    from backend.audit.testsets import relevant

    assert relevant(["prompts/grader.md"]) == {"gate"}
    assert relevant(["templates/slides/step.md", "templates/readme/x.md"]) == {"slides", "readme"}
    assert relevant(["backend/app.py"]) == set()
