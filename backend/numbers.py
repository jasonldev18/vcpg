"""Numbers a text states, for checks that output never invents one (slides, dossier)."""

import re

DIGITS = re.compile(r"\d+(?:\.\d+)?")
NAMES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty",
)  # fmt: skip
WORDS = {name: str(i) for i, name in enumerate(NAMES)}
WORD = re.compile(rf"\b({'|'.join(NAMES)})\b", re.IGNORECASE)


def numbers_in(text: str) -> set[str]:
    """Digits, plus number words as digits: "five films" supports a slide saying "5"."""
    return set(DIGITS.findall(text)) | {WORDS[m.lower()] for m in WORD.findall(text)}


def invented(output: str, sources: str) -> list[str]:
    return sorted(set(DIGITS.findall(output)) - numbers_in(sources))
