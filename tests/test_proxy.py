import json

import httpx2 as httpx

from backend import secrets
from backend.llm.proxy import KeyProxy

REAL_KEY = "sk-ant-api03-real-key-in-keychain"


def upstream(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text='event: ping\ndata: {"ok": true}\n\n')

    return httpx.MockTransport(handle)


async def test_swaps_the_session_secret_for_the_real_key() -> None:
    secrets.save("anthropic", REAL_KEY)
    seen: list[httpx.Request] = []
    async with KeyProxy(transport=upstream(seen)) as proxy, httpx.AsyncClient() as client:
        reply = await client.post(
            f"{proxy.url}/v1/messages?beta=true",
            headers={"x-api-key": proxy.secret, "anthropic-version": "2023-06-01"},
            json={"model": "claude-opus-5-5"},
        )
    assert reply.status_code == 200 and "ping" in reply.text
    [sent] = seen
    assert sent.headers["x-api-key"] == REAL_KEY
    assert sent.headers["anthropic-version"] == "2023-06-01"
    assert sent.url.path == "/v1/messages" and sent.url.params["beta"] == "true"
    assert proxy.secret not in json.dumps(dict(sent.headers))
    assert json.loads(sent.content) == {"model": "claude-opus-5-5"}


async def test_rejects_callers_without_the_session_secret() -> None:
    secrets.save("anthropic", REAL_KEY)
    seen: list[httpx.Request] = []
    async with KeyProxy(transport=upstream(seen)) as proxy, httpx.AsyncClient() as client:
        wrong = await client.post(f"{proxy.url}/v1/messages", headers={"x-api-key": "guess"})
        missing = await client.post(f"{proxy.url}/v1/messages")
    assert (wrong.status_code, missing.status_code) == (401, 401)
    assert seen == []


async def test_each_session_gets_its_own_secret_and_port() -> None:
    async with KeyProxy() as a, KeyProxy() as b:
        assert a.secret != b.secret and a.url != b.url
        assert a.url.startswith("http://127.0.0.1:")
