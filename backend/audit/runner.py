"""Audit runs: scouts report, Rook proposes fixes, code checks them and opens pull requests
(SPEC section 13, ARCHITECTURE section 11, SECURITY.md section 6)."""

import asyncio
import difflib
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

from backend import db, secrets
from backend.audit import github, policy, secrets_scan, testsets
from backend.audit.policy import FileChange, Proposal, RunState
from backend.events import bus
from backend.llm import sdk
from backend.orchestrator.context import tag
from backend.paths import REPO_ROOT, vcpg_home
from backend.redact import redact
from backend.schemas import AuditReport, RookFix, RookPlan
from backend.workspace import git, sandbox

Kind = Literal["project", "deep"]
SCOUTS = {
    "bolt": ("planner", "builder", "reviewer"),
    "echo": ("tutor", "lesson_builder", "interviewer", "grader"),
    "pixel": ("slide_writer", "readme_coach", "dossier_writer"),
}
NEVER = (
    "prompts/rook.md", "prompts/bolt.md", "prompts/echo.md", "prompts/pixel.md",
    "backend/audit/**", "calibration/**", "config/**", ".github/**", "docs/SECURITY.md",
    ".gitignore",
)  # fmt: skip
DEEP_EVERY = timedelta(days=14)
AUDIT_BOX = -1  # sandbox for running the unit tests of proposed changes
CALLS_PER_SCOUT = 200
CHANNEL = sdk.AUDIT_CHANNEL

_lock = asyncio.Lock()
_stage: dict[str, Any] = {"run_id": None, "kind": None, "stage": "OFFLINE"}


def _set_stage(stage: str, **extra: Any) -> None:
    _stage.update(stage=stage, **extra)
    bus.publish(CHANNEL, "audit_update", **_stage)


def _clone(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    git.remove_clone(dest)  # a scratch clone from an earlier run, never the vcpg repo itself
    subprocess.run(["git", "clone", "--quiet", str(REPO_ROOT), str(dest)], check=True)
    return dest


def _calls(kind: Kind, project_id: int | None, agents: tuple[str, ...]) -> list[dict[str, Any]]:
    """The calls a scout audits: one project's, or everything since the last deep scan."""
    args: list[Any]
    with db.session() as conn:
        if kind == "project":
            where, args = "project_id = ?", [project_id]
        else:
            last = conn.execute(
                "SELECT MAX(started_at) FROM audit_runs WHERE kind = 'deep' AND status = 'done'"
            ).fetchone()[0]
            where, args = "created_at > ?", [last or "0"]
        marks = ",".join("?" * len(agents))
        rows = conn.execute(
            f"SELECT id, agent, ok, error, input_ref, output_ref FROM agent_calls"
            f" WHERE {where} AND agent IN ({marks}) ORDER BY id DESC LIMIT ?",
            (*args, *agents, CALLS_PER_SCOUT),
        ).fetchall()
    return [dict(r) for r in rows]


async def _scout(name: str, calls: list[dict[str, Any]], clone: Path) -> AuditReport:
    lines = "\n".join(
        f"call {c['id']} · {c['agent']} · {'ok' if c['ok'] else 'failed: ' + (c['error'] or '')}"
        f" · input {c['input_ref']} · output {c['output_ref']}"
        for c in calls
    )
    task = "\n\n".join(
        [
            tag("calls", lines),
            tag("logs_folder", str(vcpg_home() / "logs")),
            tag("calibration", "The calibration sets are in calibration/ in your folder."),
        ]
    )
    go = asyncio.Event()
    go.set()
    return await sdk.run_agent(
        name, task, clone, AuditReport,
        project_id=None, step_id=None, allow_install=False, resume=go,
        read_only=(vcpg_home() / "logs",),
    )  # fmt: skip


async def _rook(reports: dict[str, AuditReport], clone: Path) -> RookPlan:
    task = tag(
        "reports", "\n\n".join(f"{n}:\n{r.model_dump_json(indent=1)}" for n, r in reports.items())
    )
    go = asyncio.Event()
    go.set()
    return await sdk.run_agent(
        "rook", task, clone, RookPlan,
        project_id=None, step_id=None, allow_install=False, resume=go, read_only=(),
    )  # fmt: skip


def _diff(path: str, old: str | None, new: str) -> FileChange:
    added, removed = [], []
    for line in difflib.ndiff((old or "").splitlines(), new.splitlines()):
        if line.startswith("+ "):
            added.append(line[2:])
        elif line.startswith("- "):
            removed.append(line[2:])
    return FileChange(path, "A" if old is None else "M", added, removed)


async def _unit_tests(name: str, files: dict[str, str]) -> bool:
    """The full unit suite on a clone with the change, inside the sandbox."""
    dest = _clone(git.workspace_path(AUDIT_BOX) / name)
    for path, content in files.items():
        (dest / path).parent.mkdir(parents=True, exist_ok=True)
        (dest / path).write_text(content, encoding="utf-8")
    if not sandbox.venv_has(AUDIT_BOX, "uvicorn"):
        await sandbox.run(
            AUDIT_BOX, f"pip install -q ./{name}[dev]", allow_install=True, timeout=1200
        )
    result = await sandbox.run(
        AUDIT_BOX,
        f'cd {name} && python -m pytest -q -p no:cacheprovider -m "not live and not network"',
        timeout=1200,
    )
    git.remove_clone(dest)
    return result.exit_code == 0


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:40] or "fix"


def _body(
    fix: RookFix,
    before: dict[str, float],
    after: dict[str, float],
    unit: bool,
    failures: list[str],
    auto: bool,
) -> str:
    rows = "\n".join(
        f"| {k} | {before.get(k, '-')} | {after.get(k, '-')} |" for k in sorted(before | after)
    )
    results = (
        f"| item | before | after |\n|---|---|---|\n{rows}"
        if rows
        else "No calibration set covers these files."
    )
    verdict = (
        "Merged automatically: every auto-merge rule passed."
        if auto
        else (
            "Waiting for review:\n" + "\n".join(f"- {f}" for f in failures)
            if failures
            else "Waiting for review: Rook marked this change for review."
        )
    )
    return "\n\n".join([
        f"## Problem\n{fix.problem}",
        "## Evidence\n" + "\n".join(f"- {e}" for e in fix.evidence),
        f"## Change\n{fix.change}",
        f"## Results\nUnit tests: {'pass' if unit else 'fail'}\n\n{results}",
        f"## Risk class\n{fix.risk}\n\n{verdict}",
        "_Opened by the VCPG audit crew._",
    ])  # fmt: skip


def _save_pr(
    run_id: int,
    issue_id: int | None,
    branch: str,
    url: str | None,
    auto: bool,
    state: str,
    before: Any,
    after: Any,
) -> None:
    with db.session() as conn:
        conn.execute(
            "INSERT INTO audit_prs (run_id, issue_id, branch, pr_url, auto_merge, state,"
            " before_json, after_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, issue_id, branch, url, auto, state, json.dumps(before), json.dumps(after)),
        )


def _issue(run_id: int, agent: str, severity: str, title: str, evidence: str) -> int:
    with db.session() as conn:
        issue_id = conn.execute(
            "INSERT INTO audit_issues (run_id, agent, severity, title, evidence, status)"
            " VALUES (?, ?, ?, ?, ?, 'open')",
            (run_id, agent, severity, title, evidence),
        ).lastrowid
    assert issue_id is not None
    if severity == "high":
        bus.publish(CHANNEL, "audit_siren", title=title)
    return issue_id


async def _handle(run_id: int, fix: RookFix, run: RunState, issues: dict[str, int]) -> None:
    branch = f"audit/{run_id}/{_slug(fix.slug)}"
    issue_id = next((issues[t] for t in fix.issues if t in issues), None)
    files = {f.path: f.content for f in fix.files}
    if any(fnmatch(p, n) or p == n for p in files for n in NEVER):
        _save_pr(
            run_id,
            issue_id,
            branch,
            None,
            False,
            "dropped: touches a path the audit crew may not change",
            {},
            {},
        )
        return
    if not secrets.get("github"):
        _save_pr(run_id, issue_id, branch, None, False, "not opened: no GitHub token", {}, {})
        return
    main = await github.main_sha()
    base = {p: await github.file_at(p, main) for p in files}
    changes = [_diff(p, base[p], files[p]) for p in files]
    if hits := secrets_scan.scan([line for c in changes for line in c.added]):
        title = f"Proposed change '{fix.title}' contained a secret-like string"
        _issue(run_id, "rook", "high", title, ", ".join(sorted({h.kind for h in hits})))
        _save_pr(run_id, issue_id, branch, None, False, "blocked: secret scan", {}, {})
        return
    unit = await _unit_tests(f"{run_id}-{_slug(fix.slug)}", files)
    sets = testsets.relevant(list(files))
    before = await testsets.score(sets, dict(base))
    after = await testsets.score(sets, dict(files))
    proposal = Proposal(branch, main, await github.main_sha(), changes, unit, before, after)
    failures = policy.check(proposal, run)
    auto = fix.risk == "auto" and not failures
    await github.commit_branch(main, branch, files, fix.title)
    number, url = await github.open_pr(
        branch, fix.title, _body(fix, before, after, unit, failures, auto)
    )
    state = "open"
    if auto and not await github.mergeable(number):
        auto = False  # merge conflicts mean review (rule 7)
    elif auto and await github.merge(number):
        policy.record_merge(proposal, run)
        state = "merged"
    _save_pr(run_id, issue_id, branch, url, auto and state == "merged", state, before, after)


async def run(kind: Kind, project_id: int | None = None) -> int:
    async with _lock:  # one audit at a time
        with db.session() as conn:
            run_id = conn.execute(
                "INSERT INTO audit_runs (kind, status) VALUES (?, 'running')", (kind,)
            ).lastrowid
        assert run_id is not None
        work = vcpg_home() / "audit" / str(run_id)
        try:
            _set_stage("COLLECTING REPORTS", run_id=run_id, kind=kind)
            clone = _clone(work / "clone")
            slices = {n: _calls(kind, project_id, agents) for n, agents in SCOUTS.items()}
            names = [n for n, calls in slices.items() if calls]
            reports = dict(
                zip(
                    names,
                    await asyncio.gather(*(_scout(n, slices[n], clone) for n in names)),
                    strict=True,
                )
            )
            issues = {
                i.title: _issue(
                    run_id,
                    name,
                    i.severity,
                    i.title,
                    json.dumps([e.model_dump() for e in i.evidence]),
                )
                for name, report in reports.items()
                for i in report.issues
            }
            plan = RookPlan(fixes=[])
            if issues:
                _set_stage("TRACING CAUSES")
                plan = await _rook(reports, clone)
            _set_stage("RUNNING TESTS")
            state = RunState()
            for fix in plan.fixes:
                await _handle(run_id, fix, state, issues)
            report: dict[str, Any] = {n: r.model_dump() for n, r in reports.items()}
            report["fixes"] = len(plan.fixes)
            status = "done"
        except Exception as e:
            report, status = {"error": redact(str(e))}, "failed"
        finally:
            git.remove_clone(work)
        with db.session() as conn:
            conn.execute(
                "UPDATE audit_runs SET status = ?, finished_at = CURRENT_TIMESTAMP,"
                " report_json = ? WHERE id = ?",
                (status, json.dumps(report), run_id),
            )
        _set_stage("SCAN COMPLETE" if status == "done" else "SCAN FAILED", run_id=run_id)
        _stage.update(stage="OFFLINE", run_id=None, kind=None)
        return run_id


def start(kind: Kind, project_id: int | None = None) -> None:
    """Run in the background; a second request waits for the first to finish."""
    asyncio.get_running_loop().create_task(run(kind, project_id))


def deep_scan_due() -> bool:
    """Every 14 days while the app is open, and only when there is something to audit."""
    with db.session() as conn:
        last = conn.execute(
            "SELECT MAX(started_at) FROM audit_runs WHERE kind = 'deep'"
        ).fetchone()[0]
        new_calls = conn.execute(
            "SELECT COUNT(*) FROM agent_calls WHERE created_at > ?", (last or "0",)
        ).fetchone()[0]
    if not new_calls or not secrets.get("anthropic"):
        return False
    return (
        last is None
        or datetime.now(UTC) - datetime.fromisoformat(last).replace(tzinfo=UTC) >= DEEP_EVERY
    )


async def scheduler() -> None:
    """On startup and every hour: start a deep scan when one is due."""
    while True:
        if not _lock.locked() and deep_scan_due():
            start("deep")
        await asyncio.sleep(3600)


def view() -> dict[str, Any]:
    with db.session() as conn:
        runs = [dict(r) for r in conn.execute(
            "SELECT id, kind, status, started_at, finished_at FROM audit_runs"
            " ORDER BY id DESC LIMIT 10"
        )]  # fmt: skip
        issues = [dict(r) for r in conn.execute(
            "SELECT id, run_id, agent, severity, title, evidence, status FROM audit_issues"
            " ORDER BY id DESC LIMIT 50"
        )]  # fmt: skip
        prs = [dict(r) for r in conn.execute(
            "SELECT id, run_id, issue_id, branch, pr_url, auto_merge, state, before_json,"
            " after_json FROM audit_prs ORDER BY id DESC LIMIT 50"
        )]  # fmt: skip
        last_deep = conn.execute(
            "SELECT MAX(started_at) FROM audit_runs WHERE kind = 'deep'"
        ).fetchone()[0]
    due = datetime.fromisoformat(last_deep).replace(tzinfo=UTC) + DEEP_EVERY if last_deep else None
    return {
        "current": dict(_stage) if _lock.locked() else None,
        "runs": runs,
        "issues": issues,
        "prs": prs,
        "next_deep_scan": due.isoformat() if due else None,
        "github": secrets.last_four("github") is not None,
    }
