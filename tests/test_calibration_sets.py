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
    import yaml

    from backend.lessons.retrieve import Passage
    from backend.lessons.validate import check
    from backend.paths import REPO_ROOT
    from backend.schemas import Paragraph, Section

    data = yaml.safe_load((REPO_ROOT / "calibration/lessons/planted.yaml").read_text())
    retrieved = {
        pid: Passage(pid, p["text"], p["kind"], "t", 1.0) for pid, p in data["passages"].items()
    }
    for case in data["sections"]:
        section = Section(
            kind="start_here",
            paragraphs=[Paragraph(**p) for p in case["paragraphs"]],
            visual_json="",
            code="",
            questions=[],
        )
        errors = check(section, retrieved, data["terms"])
        assert len(errors) == len(case["expect"]), f"{case['name']}: {errors}"
        for error, expected in zip(errors, case["expect"], strict=True):
            assert expected in error, case["name"]
