from backend.gate.rubric import (
    Item,
    hardest,
    hint_level,
    improved,
    merge,
    needs_reteach,
    passed,
    progress,
    quote_found,
    replay,
)
from backend.schemas import GateGrade, ItemGrade, Status

ITEMS = [Item("why normalise"), Item("cosine vs euclidean"), Item("cold start")]
ANSWERS = ["I mean-centre each user's ratings so harsh and generous raters compare fairly."]
QUOTE = "mean-centre each user's ratings"


def grade(*statuses: tuple[Status, str | None]) -> GateGrade:
    items = [
        ItemGrade(item_index=i, status=s, evidence=e, reason="r")
        for i, (s, e) in enumerate(statuses)
    ]
    return GateGrade(items=items, gap="g")


def test_merge_never_lowers_a_status() -> None:
    covered = merge(ITEMS, grade(("covered", QUOTE)), ANSWERS)
    later = merge(covered, grade(("missing", None), ("partial", QUOTE)), ANSWERS)
    assert [i.status for i in later] == ["covered", "partial", "missing"]
    assert later[0].evidence == QUOTE


def test_evidence_not_found_in_the_users_messages_becomes_missing() -> None:
    invented = merge(ITEMS, grade(("covered", "I would shard the index by user")), ANSWERS)
    no_quote = merge(ITEMS, grade(("partial", None)), ANSWERS)
    assert invented[0].status == "missing"
    assert no_quote[0].status == "missing"


def test_quote_match_ignores_case_whitespace_and_smart_quotes() -> None:
    assert quote_found("Mean-centre  each user\N{RIGHT SINGLE QUOTATION MARK}s RATINGS.", ANSWERS)
    assert not quote_found("", ANSWERS)
    assert not quote_found("median-centre", ANSWERS)


def test_grades_for_unknown_items_are_ignored() -> None:
    bogus = GateGrade(
        items=[ItemGrade(item_index=9, status="covered", evidence=QUOTE, reason="r")], gap="g"
    )
    assert merge(ITEMS, bogus, ANSWERS) == ITEMS


def test_gate_opens_only_when_every_item_is_covered() -> None:
    partly = merge(
        ITEMS, grade(("covered", QUOTE), ("covered", QUOTE), ("partial", QUOTE)), ANSWERS
    )
    assert not passed(partly)
    assert passed(merge(partly, grade(*[("covered", QUOTE)] * 3), ANSWERS))


def test_improved_detects_any_raised_item() -> None:
    after = merge(ITEMS, grade(("partial", QUOTE)), ANSWERS)
    assert improved(ITEMS, after)
    assert not improved(after, after)


def test_reteach_after_three_answers_in_a_row_with_no_progress() -> None:
    assert not needs_reteach([False, False])
    assert not needs_reteach([False, True, False])
    assert needs_reteach([True, False, False, False])


def test_hint_ladder_climbs_and_stops_at_the_code_pointer() -> None:
    assert [hint_level(n) for n in range(5)] == [1, 2, 3, 3, 3]


def test_progress_is_counts_only() -> None:
    items = merge(ITEMS, grade(("covered", QUOTE)), ANSWERS)
    assert progress(items) == {"covered": 1, "total": 3}


def test_replay_recomputes_progress_and_finds_the_hardest_item() -> None:
    texts = [i.text for i in ITEMS]
    graded = [
        (ANSWERS[0], grade(("covered", QUOTE))),
        ("I am not sure.", grade(("covered", QUOTE), ("missing", None), ("covered", QUOTE))),
        ("x", grade(("covered", QUOTE), ("covered", QUOTE))),
    ]
    states = replay(texts, graded)
    assert [progress(s)["covered"] for s in states] == [1, 2, 3]
    assert hardest(states, 3) == 1
    assert hardest(replay(texts, graded[:1]), 3) == 1  # never covered: the first such item
