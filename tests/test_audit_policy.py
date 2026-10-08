"""One test per auto-merge rule (SECURITY.md section 6), plus the secrets scan."""

from dataclasses import replace

import pytest

from backend.audit import policy, secrets_scan
from backend.audit.policy import FileChange, Proposal, RunState

WORDING = FileChange(
    "templates/slides/step.md",
    "M",
    added=["Keep each decision to one short line."],
    removed=["Keep each decision short."],
)
OK = Proposal(
    branch="audit/12/shorter-decisions",
    base_sha="abc",
    main_sha="abc",
    files=[WORDING],
    unit_tests_passed=True,
    before={"slides/knn_core": 1.0, "slides/rag_retrieval": 1.0},
    after={"slides/knn_core": 1.0, "slides/rag_retrieval": 1.0},
)


def failures(p: Proposal, run: RunState | None = None) -> list[str]:
    return policy.check(p, run or RunState())


def test_a_small_allowed_wording_change_that_passes_everything_is_merged() -> None:
    assert failures(OK) == []


@pytest.mark.parametrize(
    "path",
    ["prompts/grader.md", "backend/audit/policy.py", "docs/SECURITY.md", ".github/workflows/ci.yml",
     "calibration/gate/knn.yaml", "Makefile", "frontend/package-lock.json", "templates/rubric.md",
     "README.md", "templates/slides/../../prompts/x.md", "/templates/slides/x.md",
     r"templates\slides\..\..\prompts\x.md", "./templates/slides/x.md"],
)  # fmt: skip
def test_rules_1_and_2_paths_off_the_allowlist_or_blocked(path: str) -> None:
    [failure] = failures(replace(OK, files=[replace(WORDING, path=path)]))
    assert "allowlist" in failure


@pytest.mark.parametrize("change", [{"status": "D"}, {"status": "R"}, {"mode_changed": True}])
def test_rule_2_deletes_renames_and_permission_changes(change: dict[str, object]) -> None:
    assert any(
        "need review" in f for f in failures(replace(OK, files=[replace(WORDING, **change)]))
    )  # type: ignore[arg-type]


def test_rule_3_size_cap() -> None:
    many = [replace(WORDING, path=f"templates/slides/{i}.md") for i in range(4)]
    assert any("too large" in f for f in failures(replace(OK, files=many)))
    long = replace(WORDING, added=["line"] * 61, removed=[])
    assert any("61 changed lines" in f for f in failures(replace(OK, files=[long])))


@pytest.mark.parametrize("word", ["never", "Must", "do not", "only", "always", "cite", "rubric"])
def test_rule_4_removing_a_rule_line(word: str) -> None:
    weakened = replace(WORDING, removed=[f"You {word} state a number the inputs lack."])
    assert any("rule line" in f for f in failures(replace(OK, files=[weakened])))


def test_rule_5_a_key_in_the_diff_blocks() -> None:
    leaked = replace(WORDING, added=["example: sk-ant-api03-AbCdEfGhIjKlMnOp"])
    assert any("secret scan: Anthropic key" in f for f in failures(replace(OK, files=[leaked])))


def test_rule_6_failing_unit_tests_or_one_worse_calibration_item() -> None:
    assert "unit tests fail" in failures(replace(OK, unit_tests_passed=False))
    worse = {"slides/knn_core": 1.0, "slides/rag_retrieval": 0.5}
    assert any("slides/rag_retrieval" in f for f in failures(replace(OK, after=worse)))
    missing = {"slides/knn_core": 1.0}
    assert any("worse" in f for f in failures(replace(OK, after=missing)))


def test_rule_7_branch_base_and_conflicts() -> None:
    assert any("branch" in f for f in failures(replace(OK, branch="fix/whatever")))
    assert "not based on current main" in failures(replace(OK, base_sha="old"))
    assert "merge conflicts" in failures(replace(OK, mergeable=False))


def test_rule_8_rate_limits() -> None:
    run = RunState()
    for i in range(3):
        p = replace(OK, files=[replace(WORDING, path=f"templates/slides/{i}.md")])
        assert failures(p, run) == []
        policy.record_merge(p, run)
    assert any("already auto-merged 3" in f for f in failures(OK, run))
    one = RunState()
    policy.record_merge(OK, one)
    assert any("already auto-merged this run" in f for f in failures(OK, one))


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("key = 'sk-ant-api03-AbCdEfGhIjKlMn0p'", "Anthropic key"),
        ("token: github_pat_11ABCDEFG0123456789_abcdefXYZ", "GitHub token"),
        ("ghp_abcdefghijklmnopqrstuvwxyz0123456789", "GitHub token"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----", "private key"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private key"),
        ("url = https://user:hunter2@example.com/repo", "URL with credentials"),
        ("secret = 'q8Zr4Lw2Xv9Kt1Hn7Bc3Dm6Pf0Ys5Ja'", "high-entropy string"),
    ],
)
def test_secrets_scan_catches(line: str, kind: str) -> None:
    assert kind in {f.kind for f in secrets_scan.scan([line])}


@pytest.mark.parametrize(
    "line",
    [
        "Keep each decision to one short line.",
        "def test_reviewer_cuts_unreachable_code_and_keeps_boundaries():",
        "https://scikit-learn.org/stable/modules/neighbors.html",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ],
)
def test_secrets_scan_ignores_ordinary_text(line: str) -> None:
    assert secrets_scan.scan([line]) == []
