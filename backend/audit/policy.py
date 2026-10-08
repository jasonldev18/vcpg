"""Audit auto-merge rules (SECURITY.md section 6). Every check must pass; anything else waits for
the user's review. This file is itself on the blocked list, so no audit can change it."""

import posixpath
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch

from backend.audit import secrets_scan

ALLOWED = ("templates/slides/**", "templates/readme/**", "content/quizzes/**")
BLOCKED = (
    "prompts/**", "backend/**", "frontend/**", "config/**", ".github/**", ".gitignore",
    "Makefile", "pyproject.toml", "package.json", "*package.json", "*lock*", "docs/**",
    "calibration/**", "*rubric*", "*threshold*",
)  # fmt: skip
MAX_FILES, MAX_LINES = 3, 60
MAX_AUTO_MERGES_PER_RUN = 3
RULE_WORDS = re.compile(r"\b(never|must|do not|only|always|cite|rubric)\b", re.IGNORECASE)
BRANCH = re.compile(r"^audit/\d+/[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str  # "A" added, "M" modified, "D" deleted, "R" renamed
    added: list[str]
    removed: list[str]
    mode_changed: bool = False


@dataclass(frozen=True)
class Proposal:
    branch: str
    base_sha: str
    main_sha: str
    files: list[FileChange]
    unit_tests_passed: bool
    before: dict[str, float]  # calibration item -> score, on main
    after: dict[str, float]  # the same items with the change
    mergeable: bool = True


@dataclass
class RunState:
    auto_merges: int = 0
    merged_files: set[str] = field(default_factory=set)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(path, p) or fnmatch(path, p.removesuffix("/**")) for p in patterns)


def _normal(path: str) -> bool:
    """Globs match text, so "templates/slides/../../prompts/x" must never reach them."""
    return (
        posixpath.normpath(path) == path and not path.startswith(("/", "..")) and "\\" not in path
    )


def check(p: Proposal, run: RunState) -> list[str]:
    """Why this change may not be merged automatically; empty means it may."""
    failures = []
    for f in p.files:  # rules 1 and 2
        if (f.status != "M" and f.status != "A") or f.mode_changed:
            failures.append(f"{f.path}: deleted, renamed or permission changes need review")
        if not _normal(f.path) or _matches(f.path, BLOCKED) or not _matches(f.path, ALLOWED):
            failures.append(f"{f.path}: not on the auto-merge allowlist")
    lines = sum(len(f.added) + len(f.removed) for f in p.files)  # rule 3
    if len(p.files) > MAX_FILES or lines > MAX_LINES:
        failures.append(f"too large: {len(p.files)} files, {lines} changed lines")
    for f in p.files:  # rule 4
        for line in f.removed:
            if RULE_WORDS.search(line):
                failures.append(f"{f.path}: removes or changes a rule line: {line.strip()}")
    if hits := secrets_scan.scan([line for f in p.files for line in f.added]):  # rule 5
        failures.append(f"secret scan: {', '.join(sorted({h.kind for h in hits}))}")
    if not p.unit_tests_passed:  # rule 6
        failures.append("unit tests fail")
    worse = [item for item, score in p.before.items() if p.after.get(item, float("-inf")) < score]
    if worse:
        failures.append(f"calibration got worse on: {', '.join(sorted(worse))}")
    if not BRANCH.match(p.branch):  # rule 7
        failures.append(f"branch {p.branch} is not audit/<run_id>/<slug>")
    if p.base_sha != p.main_sha:
        failures.append("not based on current main")
    if not p.mergeable:
        failures.append("merge conflicts")
    if run.auto_merges >= MAX_AUTO_MERGES_PER_RUN:  # rule 8
        failures.append("this run already auto-merged 3 changes")
    if repeated := sorted({f.path for f in p.files} & run.merged_files):
        failures.append(f"already auto-merged this run: {', '.join(repeated)}")
    return failures


def record_merge(p: Proposal, run: RunState) -> None:
    run.auto_merges += 1
    run.merged_files |= {f.path for f in p.files}
