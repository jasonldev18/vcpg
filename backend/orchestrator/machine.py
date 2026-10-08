"""Step states and the only transitions allowed between them (ARCHITECTURE section 3)."""

from enum import StrEnum


class State(StrEnum):
    PLANNED = "planned"
    TAUGHT = "taught"
    BUILT = "built"
    REVIEWED = "reviewed"
    TOURED = "toured"
    INTERVIEWING = "interviewing"
    PASSED = "passed"
    SLIDE_DONE = "slide_done"
    BLOCKED = "blocked"


S = State
TRANSITIONS: frozenset[tuple[State, State]] = frozenset(
    {
        (S.PLANNED, S.TAUGHT),  # user clicks Ready, build it
        (S.TAUGHT, S.BUILT),  # builder finishes
        (S.BUILT, S.REVIEWED),  # tests pass
        (S.BUILT, S.TAUGHT),  # user stops the build
        (S.BUILT, S.BUILT),  # review failed: builder retries once
        (S.BUILT, S.BLOCKED),  # review failed twice
        (S.BLOCKED, S.TAUGHT),  # Retry build
        (S.BLOCKED, S.PLANNED),  # Edit plan
        (S.REVIEWED, S.TOURED),  # user clicks Ready for interview
        (S.TOURED, S.INTERVIEWING),  # first question asked
        (S.INTERVIEWING, S.INTERVIEWING),  # answer graded, hint, re-teach
        (S.INTERVIEWING, S.PASSED),  # every rubric item covered
        (S.PASSED, S.SLIDE_DONE),  # slide written
    }
)


class InvalidTransition(Exception):
    pass


def transition(current: State, target: State) -> State:
    if (current, target) not in TRANSITIONS:
        raise InvalidTransition(f"A step cannot go from {current} to {target}.")
    return target
