"""Audit runs end to end with fake agents and a fake GitHub (SECURITY.md section 6)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend import db, secrets
from backend.audit import github, runner, testsets
from backend.llm import sdk
from backend.schemas import AuditIssue, AuditReport, Evidence, NewFile, RookFix, RookPlan

TOKEN = "github_pat_11AAAAAAA0123456789_abcdefghijklmnopqrstuvwxyz"
OLD_SLIDE = "Keep each decision short.\nNever invent a number.\n"


def fix(slug: str, path: str, content: str, risk: str = "auto") -> RookFix:
    return RookFix(
        slug=slug,
        title=f"Fix {slug}",
        issues=["Slides state numbers the code lacks"],
        problem="p",
        evidence=["call 3: '99% precision'"],
        change="c",
        files=[NewFile(path=path, content=content)],
        risk=risk,  # type: ignore[arg-type]
    )


PLAN = RookPlan(
    fixes=[
        fix(
            "slide-wording",
            "templates/slides/step.md",
            "Keep each decision to one line.\nNever invent a number.\n",
        ),
        fix("grader-wording", "prompts/grader.md", "new grader prompt", risk="review"),
        fix("loosen-policy", "backend/audit/policy.py", "MAX_FILES = 99"),
        fix("leaky", "templates/slides/other.md", "token sk-ant-api03-AbCdEfGhIjKlMnOpQr\n"),
    ]
)


class FakeGitHub:
    def __init__(self) -> None:
        self.commits: list[tuple[str, dict[str, str]]] = []
        self.prs: list[tuple[str, str]] = []
        self.merged: list[int] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def main_sha() -> str:
            return "main1"

        async def file_at(path: str, ref: str) -> str | None:
            return OLD_SLIDE if path.startswith("templates/") else "old"

        async def commit_branch(base: str, branch: str, files: dict[str, str], message: str) -> str:
            assert base == "main1"
            self.commits.append((branch, files))
            return "c1"

        async def open_pr(branch: str, title: str, body: str) -> tuple[int, str]:
            self.prs.append((branch, body))
            return len(self.prs), f"https://github.com/pr/{len(self.prs)}"

        async def mergeable(number: int) -> bool:
            return True

        async def merge(number: int) -> bool:
            self.merged.append(number)
            return True

        for name, fn in locals().items():
            if name != "self" and callable(fn):
                monkeypatch.setattr(github, name, fn)


@pytest.fixture
def audit(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    with db.session() as conn:
        for agent in ("slide_writer", "grader", "builder"):
            conn.execute(
                "INSERT INTO agent_calls (agent, model, effort, runtime, ok, duration_ms)"
                " VALUES (?, 'claude-opus-5-5', 'high', 'api', 1, 10)",
                (agent,),
            )
    seen: list[dict[str, Any]] = []

    async def run_agent(agent: str, task: str, cwd: Path, schema: type[Any], **kw: Any) -> Any:
        seen.append({"agent": agent, "task": task, "cwd": cwd, **kw})
        assert kw["read_only"] is not None and kw["project_id"] is None
        if agent == "rook":
            return PLAN
        issue = AuditIssue(
            title="Slides state numbers the code lacks" if agent == "pixel" else f"{agent} issue",
            severity="high" if agent == "pixel" else "low",
            agent="slide_writer",
            evidence=[Evidence(call_id=1, excerpt="99% precision")],
            suspected_cause="c",
            suggested_fix="f",
        )
        return AuditReport(issues=[issue])

    async def unit_tests(name: str, files: dict[str, str]) -> bool:
        return True

    async def score(names: set[str], files: dict[str, str | None]) -> dict[str, float]:
        return {"slides/knn_core": 1.0} if "slides" in names else {}

    monkeypatch.setattr(sdk, "run_agent", run_agent)
    monkeypatch.setattr(runner, "_unit_tests", unit_tests)
    monkeypatch.setattr(testsets, "score", score)
    fake = FakeGitHub()
    fake.install(monkeypatch)
    fake.seen = seen  # type: ignore[attr-defined]
    return fake


def prs() -> dict[str, dict[str, Any]]:
    with db.session() as conn:
        return {
            r["branch"].split("/")[-1]: dict(r) for r in conn.execute("SELECT * FROM audit_prs")
        }


async def test_a_deep_scan_merges_only_what_policy_allows(audit: FakeGitHub) -> None:
    secrets.save("github", TOKEN)
    run_id = await runner.run("deep")

    agents = [s["agent"] for s in audit.seen]  # type: ignore[attr-defined]
    assert sorted(agents[:3]) == ["bolt", "echo", "pixel"] and agents[3] == "rook"
    pixel_task = next(s["task"] for s in audit.seen if s["agent"] == "pixel")  # type: ignore[attr-defined]
    assert "slide_writer" in pixel_task and "builder" not in pixel_task  # each scout gets its slice

    result = prs()
    assert (
        result["slide-wording"]["state"] == "merged" and result["slide-wording"]["auto_merge"] == 1
    )
    assert (
        result["grader-wording"]["state"] == "open" and result["grader-wording"]["auto_merge"] == 0
    )
    assert result["loosen-policy"]["state"].startswith("dropped")
    assert result["leaky"]["state"] == "blocked: secret scan"
    assert audit.merged == [1]
    assert [b for b, _ in audit.commits] == [
        f"audit/{run_id}/slide-wording",
        f"audit/{run_id}/grader-wording",
    ]
    assert "| slides/knn_core | 1.0 | 1.0 |" in audit.prs[0][1]
    assert "not on the auto-merge allowlist" in audit.prs[1][1]

    with db.session() as conn:
        run = conn.execute("SELECT status FROM audit_runs WHERE id = ?", (run_id,)).fetchone()
        severities = [r[0] for r in conn.execute("SELECT severity FROM audit_issues")]
    assert run["status"] == "done"
    assert severities.count("high") == 2  # pixel's issue and the blocked secret


async def test_without_a_github_token_fixes_are_recorded_not_opened(audit: FakeGitHub) -> None:
    await runner.run("deep")
    assert {p["state"] for name, p in prs().items() if name != "loosen-policy"} == {
        "not opened: no GitHub token"
    }
    assert audit.commits == [] and audit.prs == []


def test_deep_scans_are_due_every_14_days_when_there_is_something_to_audit() -> None:
    assert not runner.deep_scan_due()  # no calls yet
    with db.session() as conn:
        conn.execute(
            "INSERT INTO agent_calls (agent, model, effort, runtime, ok, duration_ms)"
            " VALUES ('grader', 'm', 'high', 'api', 1, 1)"
        )
    assert not runner.deep_scan_due()  # no Anthropic key
    secrets.save("anthropic", "sk-ant-api03-test-key-0000")
    assert runner.deep_scan_due()
    recent = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    with db.session() as conn:
        conn.execute(
            "INSERT INTO audit_runs (kind, status, started_at) VALUES ('deep', 'done', ?)",
            (recent,),
        )
        conn.execute(
            "INSERT INTO agent_calls (agent, model, effort, runtime, ok, duration_ms, created_at)"
            " VALUES ('grader', 'm', 'high', 'api', 1, 1, CURRENT_TIMESTAMP)"
        )
    assert not runner.deep_scan_due()


def test_audit_state_and_manual_run(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    monkeypatch.setattr(runner, "start", lambda kind, project_id=None: started.append(kind))
    view = api.post("/api/audit/run").json()
    assert started == ["deep"]
    assert set(view) == {"current", "runs", "issues", "prs", "next_deep_scan", "github"}
