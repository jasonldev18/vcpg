import pytest

from labels import parse_label, run


def test_parses_a_label() -> None:
    assert parse_label('{"label": "positive"}') == "positive"


@pytest.mark.parametrize("reply", ["not json", '{"label": "angry"}', "[1, 2]"])
def test_rejects_bad_replies(reply: str) -> None:
    with pytest.raises(ValueError):
        parse_label(reply)


def test_counts() -> None:
    replies = ['{"label": "positive"}', '{"label": "positive"}', '{"label": "neutral"}']
    assert run(replies) == {"positive": 2, "negative": 0, "neutral": 1}
