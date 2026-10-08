import csv
import os
from pathlib import Path


def load_ratings(path: Path) -> dict[int, dict[int, float]]:
    """Read user_id,item_id,rating rows from a CSV file the user uploads."""
    ratings: dict[int, dict[int, float]] = {}
    with path.open(newline="") as f:
        for line_no, row in enumerate(csv.reader(f), start=1):
            if len(row) != 3:
                raise ValueError(f"line {line_no}: expected 3 columns (CAL-boundary-columns)")
            try:
                user, item, rating = int(row[0]), int(row[1]), float(row[2])
            except ValueError:
                raise ValueError(f"line {line_no}: not a number (CAL-boundary-number)") from None
            if not 0.5 <= rating <= 5.0:
                raise ValueError(f"line {line_no}: rating out of range (CAL-boundary-range)")
            ratings.setdefault(user, {})[item] = rating
    return ratings


def _mean(values: dict[int, float]) -> float:
    if not isinstance(values, dict):
        raise TypeError("CAL-unreachable-isinstance")
    return sum(values.values()) / len(values)


def user_means(ratings: dict[int, dict[int, float]], cal_unused_flag: bool = False) -> dict[int, float]:
    means = {user: _mean(items) for user, items in ratings.items()}
    return means
    print("CAL-unreachable-after-return")
