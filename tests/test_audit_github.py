"""GitHub token checks and API-only branches and pull requests, against a mock GitHub."""

import base64
import json
from collections.abc import Callable

import httpx2 as httpx
import pytest

from backend import secrets
from backend.audit import github

REPO = "jasonldev18/vcpg"
TOKEN = "github_pat_11AAAAAAA0123456789_abcdefghijklmnopqrstuvwxyz"


def fake(responses: dict[str, int], repos: list[str] | None = None) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/user/repos":
            return httpx.Response(200, json=[{"full_name": r} for r in (repos or [REPO])])
        return httpx.Response(responses.get(path, 404), json={})

    github.transport = httpx.MockTransport(handle)
    return seen


@pytest.fixture(autouse=True)
def no_real_github() -> None:
    github.transport = httpx.MockTransport(lambda r: httpx.Response(599))
    yield
    github.transport = None


@pytest.fixture(autouse=True)
def repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(github, "repo_slug", lambda: REPO)


ALLOWED = {f"/repos/{REPO}": 200, f"/repos/{REPO}/contents/": 200, f"/repos/{REPO}/pulls": 200}


async def test_a_contents_and_pull_requests_token_is_accepted() -> None:
    seen = fake(ALLOWED)
    result = await github.check_token(TOKEN)
    assert result.ok, result.problems
    assert result.found == ["Metadata: read", "Contents: read", "Pull requests: read"]
    assert all(r.headers["Authorization"] == f"Bearer {TOKEN}" for r in seen)
    assert all(r.url.host == "api.github.com" for r in seen)


@pytest.mark.parametrize(
    ("path", "problem"),
    [
        (f"/repos/{REPO}/keys", "Has Administration"),
        (f"/repos/{REPO}/actions/permissions", "Has Administration"),
        (f"/repos/{REPO}/actions/secrets", "Has Secrets"),
        ("/user/emails", "Has account permissions"),
    ],
)
async def test_broader_tokens_are_refused(path: str, problem: str) -> None:
    fake({**ALLOWED, path: 200})
    result = await github.check_token(TOKEN)
    assert not result.ok and problem in result.problems


async def test_access_to_other_repos_is_refused() -> None:
    fake(ALLOWED, repos=[REPO, "jasonldev18/private-notes"])
    assert "Can access repositories other than vcpg" in (await github.check_token(TOKEN)).problems


async def test_classic_tokens_and_unreadable_repos_are_refused() -> None:
    assert not (await github.check_token("ghp_" + "a" * 36)).ok
    fake({})
    assert "cannot read" in (await github.check_token(TOKEN)).problems[0]


def scripted(
    routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]],
) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return routes[(request.method, request.url.path)](request)

    github.transport = httpx.MockTransport(handle)
    return seen


async def test_branches_commits_and_pull_requests_go_through_the_api() -> None:
    secrets.save("github", TOKEN)
    r = f"/repos/{REPO}"
    seen = scripted(
        {
            ("GET", f"{r}/git/commits/base1"): lambda _: httpx.Response(
                200, json={"tree": {"sha": "tree0"}}
            ),
            ("POST", f"{r}/git/trees"): lambda _: httpx.Response(201, json={"sha": "tree1"}),
            ("POST", f"{r}/git/commits"): lambda _: httpx.Response(201, json={"sha": "c1"}),
            ("POST", f"{r}/git/refs"): lambda _: httpx.Response(201, json={}),
            ("POST", f"{r}/pulls"): lambda _: httpx.Response(
                201, json={"number": 7, "html_url": "https://pr/7"}
            ),
            ("GET", f"{r}/pulls/7"): lambda _: httpx.Response(200, json={"mergeable": True}),
            ("PUT", f"{r}/pulls/7/merge"): lambda _: httpx.Response(200, json={"merged": True}),
            ("GET", f"{r}/contents/templates/slides/step.md"): lambda _: httpx.Response(
                200, json={"content": base64.b64encode(b"old text").decode()}
            ),
        }
    )
    files = {"templates/slides/step.md": "new text"}
    assert await github.commit_branch("base1", "audit/3/wording", files, "Tighten wording") == "c1"
    assert await github.open_pr("audit/3/wording", "Tighten wording", "body") == (7, "https://pr/7")
    assert await github.mergeable(7) and await github.merge(7)
    assert await github.file_at("templates/slides/step.md", "main") == "old text"

    bodies = {(q.method, q.url.path): json.loads(q.content or b"{}") for q in seen}
    assert bodies[("POST", f"{r}/git/trees")]["base_tree"] == "tree0"
    assert bodies[("POST", f"{r}/git/commits")]["parents"] == ["base1"]
    assert bodies[("POST", f"{r}/git/refs")] == {"ref": "refs/heads/audit/3/wording", "sha": "c1"}
    assert bodies[("PUT", f"{r}/pulls/7/merge")] == {"merge_method": "merge"}
    assert all(TOKEN not in str(q.url) for q in seen)  # header only, never in a URL


async def test_no_token_means_no_github_calls() -> None:
    from backend.errors import Conflict

    with pytest.raises(Conflict, match="Add a GitHub token"):
        await github.main_sha()
