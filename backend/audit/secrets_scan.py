"""A gitleaks-style scan of added lines (SECURITY.md section 6, rule 5). Any hit blocks the PR."""

import math
import re
from collections import Counter
from dataclasses import dataclass

PATTERNS = {
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    "GitHub token": re.compile(r"\b(?:github_pat_|ghp_|gho_|ghs_|ghu_|ghr_)[A-Za-z0-9_]{10,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "URL with credentials": re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
}
TOKEN = re.compile(r"[A-Za-z0-9+/=_\-]{21,}")
ENTROPY = 4.0  # bits per character; random keys sit well above prose and identifiers


@dataclass(frozen=True)
class Finding:
    kind: str
    line: str


def entropy(text: str) -> float:
    counts = Counter(text)
    return -sum(n / len(text) * math.log2(n / len(text)) for n in counts.values())


def _random_looking(token: str) -> bool:
    has_mix = (
        bool(re.search(r"[A-Z]", token))
        + bool(re.search(r"[a-z]", token))
        + bool(re.search(r"[0-9]", token))
    )
    return has_mix >= 2 and entropy(token) > ENTROPY


def scan(added_lines: list[str]) -> list[Finding]:
    findings = []
    for line in added_lines:
        for kind, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding(kind, line))
        if any(_random_looking(t) for t in TOKEN.findall(line)):
            findings.append(Finding("high-entropy string", line))
    return findings
