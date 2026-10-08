"""A loopback proxy so Agent SDK sessions never hold the API key (SECURITY.md section 2).

The CLI gets a random per-session secret as its "key" and this proxy as its base URL. The
proxy checks the secret, swaps in the real key from the keychain, and streams the reply.
"""

import asyncio
from collections.abc import AsyncIterator
from hmac import compare_digest
from secrets import token_urlsafe
from types import TracebackType

import httpx2 as httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from backend import secrets

UPSTREAM = "https://api.anthropic.com"
DROP_REQUEST = {"host", "x-api-key", "authorization", "content-length"}
DROP_RESPONSE = {"content-length", "transfer-encoding", "connection", "content-encoding"}


class KeyProxy:
    def __init__(self, upstream: str = UPSTREAM, transport: httpx.AsyncBaseTransport | None = None):
        self.secret = token_urlsafe(32)
        self.url = ""
        self._client = httpx.AsyncClient(base_url=upstream, transport=transport, timeout=None)
        app = Starlette(routes=[Route("/{path:path}", self._forward, methods=["GET", "POST"])])
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(config)
        self._task: asyncio.Task[None] | None = None

    async def _forward(self, request: Request) -> Response:
        if not compare_digest(request.headers.get("x-api-key", ""), self.secret):
            return JSONResponse({"error": "unknown session"}, status_code=401)
        key = secrets.get("anthropic")
        if not key:
            return JSONResponse({"error": "no Anthropic key saved"}, status_code=401)
        headers = {k: v for k, v in request.headers.items() if k.lower() not in DROP_REQUEST}
        upstream = self._client.build_request(
            request.method,
            request.url.path,
            params=request.query_params,
            headers=headers | {"x-api-key": key},
            content=await request.body(),
        )
        reply = await self._client.send(upstream, stream=True)

        async def body() -> AsyncIterator[bytes]:
            try:
                async for chunk in reply.aiter_bytes():
                    yield chunk
            finally:
                await reply.aclose()

        return StreamingResponse(
            body(),
            status_code=reply.status_code,
            headers={k: v for k, v in reply.headers.items() if k.lower() not in DROP_RESPONSE},
        )

    async def __aenter__(self) -> "KeyProxy":
        self._task = asyncio.create_task(self._server.serve())
        while not self._server.started:
            if self._task.done():
                self._task.result()
            await asyncio.sleep(0.01)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        return self

    async def __aexit__(
        self, *exc: type[BaseException] | BaseException | TracebackType | None
    ) -> None:
        self._server.should_exit = True
        if self._task:
            await self._task
        await self._client.aclose()
