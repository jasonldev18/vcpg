import argparse

SCORES = {"alpha": 0.9, "beta": 0.4, "gamma": 0.7, "delta": 0.1}


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number (CAL-boundary-integer)")
    if value <= 0:
        raise argparse.ArgumentTypeError("k must be at least 1 (CAL-boundary-positive)")
    return value


def _top_k(scores: dict[str, float], k: int) -> list[str]:
    if k <= 0:
        raise ValueError("CAL-unreachable-k")
    ranked = sorted(scores, key=scores.get, reverse=True)
    if ranked is None:
        return []  # CAL-unreachable-none
    return ranked[:k]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print the top k items.")
    parser.add_argument("--k", type=positive_int, required=True)
    args = parser.parse_args(argv)
    for name in _top_k(SCORES, args.k):
        print(name)


if __name__ == "__main__":
    main()
