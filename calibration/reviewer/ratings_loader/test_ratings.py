from pathlib import Path

import pytest

from ratings import load_ratings, user_means


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ratings.csv"
    path.write_text(text)
    return path


def test_loads_rows_by_user(tmp_path: Path) -> None:
    ratings = load_ratings(write(tmp_path, "1,10,4.0\n1,11,2.0\n2,10,5\n"))
    assert ratings == {1: {10: 4.0, 11: 2.0}, 2: {10: 5.0}}


def test_means(tmp_path: Path) -> None:
    ratings = load_ratings(write(tmp_path, "1,10,4.0\n1,11,2.0\n2,10,5\n"))
    assert user_means(ratings) == {1: 3.0, 2: 5.0}


@pytest.mark.parametrize("text", ["1,10\n", "1,x,4\n", "1,10,9\n"])
def test_bad_rows_name_the_line(tmp_path: Path, text: str) -> None:
    with pytest.raises(ValueError, match="line 1"):
        load_ratings(write(tmp_path, text))
