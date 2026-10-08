from tests.calibration import STYLES, gate_sets


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
