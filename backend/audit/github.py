"""GitHub REST calls for the audit crew (SECURITY.md section 3).

The token is read from the keychain for each call and only ever sent as an HTTP header from
this process: no git push, no token in a command line, environment or agent session.
Branches, commits and pull requests are all made through the API.
"""

import asyncio
import base64
import re
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx2 as httpx

from backend import secrets
from backend.errors import Conflict
from backend.paths import REPO_ROOT

API = "https://api.github.com"
transport: httpx.AsyncBaseTransport | None = None  # unit tests swap in a mock


def repo_slug() -> str:
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise Conflict("The vcpg repo has no GitHub remote named origin.")
    return match.group(1)


@asynccontextmanager
async def _client(token: str | None = None) -> AsyncIterator[httpx.AsyncClient]:
    token = token or secrets.get("github")
    if not token:
        raise Conflict("Add a GitHub token in Core access to open pull requests.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(
        base_url=API, headers=headers, transport=transport, timeout=30
    ) as client:
        yield client


@dataclass
class TokenCheck:
    found: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


# A 200 from any of these means the token can do more than the audit crew needs.
TOO_BROAD = {
    "/repos/{repo}/keys": "Administration",
    "/repos/{repo}/actions/permissions": "Administration",
    "/repos/{repo}/actions/secrets": "Secrets",
    "/repos/{repo}/hooks": "Webhooks",
    "/user/emails": "account permissions",
    "/user/keys": "account permissions",
}


async def check_token(token: str) -> TokenCheck:
    """Only Contents and Pull requests on the vcpg repo. GitHub cannot list a fine-grained
    token's permissions, so this probes; Workflows and Actions write cannot be probed."""
    result = TokenCheck()
    if not token.startswith("github_pat_"):
        result.problems.append("Use a fine-grained personal access token (github_pat_…).")
        return result
    repo = repo_slug()
    async with _client(token) as gh:
        if (await gh.get(f"/repos/{repo}")).status_code != 200:
            result.problems.append(f"The token cannot read {repo}.")
            return result
        result.found.append("Metadata: read")
        if (await gh.get(f"/repos/{repo}/contents/")).status_code == 200:
            result.found.append("Contents: read")
        if (await gh.get(f"/repos/{repo}/pulls", params={"per_page": 1})).status_code == 200:
            result.found.append("Pull requests: read")
        for path, permission in TOO_BROAD.items():
            if (await gh.get(path.format(repo=repo))).status_code == 200:
                result.found.append(f"{permission} ({path.format(repo=repo)})")
                if f"Has {permission}" not in result.problems:
                    result.problems.append(f"Has {permission}")
        repos = await gh.get("/user/repos", params={"per_page": 100})
        others = [r["full_name"] for r in repos.json()] if repos.status_code == 200 else []
        if any(name.lower() != repo.lower() for name in others):
            result.problems.append("Can access repositories other than vcpg")
    return result


async def main_sha() -> str:
    async with _client() as gh:
        reply = await gh.get(f"/repos/{repo_slug()}/git/ref/heads/main")
        reply.raise_for_status()
        return str(reply.json()["object"]["sha"])


async def file_at(path: str, ref: str) -> str | None:
    async with _client() as gh:
        reply = await gh.get(f"/repos/{repo_slug()}/contents/{path}", params={"ref": ref})
    if reply.status_code == 404:
        return None
    reply.raise_for_status()
    return base64.b64decode(reply.json()["content"]).decode("utf-8")


async def commit_branch(base_sha: str, branch: str, files: dict[str, str], message: str) -> str:
    """One commit on a new branch, built from blobs and a tree through the API."""
    repo = repo_slug()
    async with _client() as gh:
        base = (await gh.get(f"/repos/{repo}/git/commits/{base_sha}")).json()
        tree = await gh.post(
            f"/repos/{repo}/git/trees",
            json={
                "base_tree": base["tree"]["sha"],
                "tree": [
                    {"path": p, "mode": "100644", "type": "blob", "content": c}
                    for p, c in files.items()
                ],
            },
        )
        tree.raise_for_status()
        commit = await gh.post(
            f"/repos/{repo}/git/commits",
            json={"message": message, "tree": tree.json()["sha"], "parents": [base_sha]},
        )
        commit.raise_for_status()
        ref = await gh.post(
            f"/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": commit.json()["sha"]},
        )
        ref.raise_for_status()
        return str(commit.json()["sha"])


async def open_pr(branch: str, title: str, body: str) -> tuple[int, str]:
    async with _client() as gh:
        reply = await gh.post(
            f"/repos/{repo_slug()}/pulls",
            json={"title": title, "head": branch, "base": "main", "body": body},
        )
        reply.raise_for_status()
        return int(reply.json()["number"]), str(reply.json()["html_url"])


async def mergeable(number: int) -> bool:
    """GitHub computes mergeability in the background; null means not decided yet."""
    async with _client() as gh:
        for _ in range(10):
            state = (await gh.get(f"/repos/{repo_slug()}/pulls/{number}")).json().get("mergeable")
            if state is not None:
                return bool(state)
            await asyncio.sleep(2)
    return False


async def merge(number: int) -> bool:
    """A normal merge through the pull request API (never a force push)."""
    async with _client() as gh:
        reply = await gh.put(
            f"/repos/{repo_slug()}/pulls/{number}/merge", json={"merge_method": "merge"}
        )
    return reply.status_code == 200
