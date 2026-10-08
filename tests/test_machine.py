import itertools

import pytest

from backend.orchestrator.machine import TRANSITIONS, InvalidTransition, State, transition

S = State
ALLOWED = {
    (S.PLANNED, S.TAUGHT),
    (S.TAUGHT, S.BUILT),
    (S.BUILT, S.REVIEWED),
    (S.BUILT, S.TAUGHT),
    (S.BUILT, S.BUILT),
    (S.BUILT, S.BLOCKED),
    (S.BLOCKED, S.TAUGHT),
    (S.BLOCKED, S.PLANNED),
    (S.REVIEWED, S.TOURED),
    (S.TOURED, S.INTERVIEWING),
    (S.INTERVIEWING, S.INTERVIEWING),
    (S.INTERVIEWING, S.PASSED),
    (S.PASSED, S.SLIDE_DONE),
}
EVERY_PAIR = list(itertools.product(State, State))


def test_table_matches_the_architecture_doc() -> None:
    assert TRANSITIONS == ALLOWED


@pytest.mark.parametrize(("current", "target"), sorted(ALLOWED))
def test_allowed_transition(current: State, target: State) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize(("current", "target"), [p for p in EVERY_PAIR if p not in ALLOWED])
def test_disallowed_transition_raises(current: State, target: State) -> None:
    with pytest.raises(InvalidTransition):
        transition(current, target)
