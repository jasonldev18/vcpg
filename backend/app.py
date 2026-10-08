import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from hmac import compare_digest
from secrets import token_urlsafe

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend import db, redact
from backend.audit import runner as audit_runner
from backend.errors import Conflict, NotFound
from backend.llm.client import LLMError, MissingKey
from backend.orchestrator.machine import InvalidTransition
from backend.routes import (
    archive,
    audit,
    core,
    deck,
    discovery,
    events,
    projects,
    squad,
    steps,
)

HOST = "127.0.0.1"  # never 0.0.0.0 (SECURITY.md section 8)
PORT = 8000
UI_ORIGIN = "http://127.0.0.1:5173"
TOKEN_HEADER = "X-VCPG-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    redact.install()
    db.connect().close()  # apply migrations before the first request
    scheduler = asyncio.create_task(audit_runner.scheduler())
    yield
    scheduler.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="VCPG", lifespan=lifespan)
    token = token_urlsafe(32)  # per launch; only the UI origin can read it, thanks to CORS

    @app.middleware("http")
    async def require_token(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in SAFE_METHODS and not compare_digest(
            request.headers.get(TOKEN_HEADER, ""), token
        ):
            return JSONResponse({"detail": "missing or wrong session token"}, status_code=403)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[UI_ORIGIN],
        allow_methods=["*"],
        allow_headers=["Content-Type", TOKEN_HEADER],
    )
    # Blocks DNS rebinding: a foreign page resolved to 127.0.0.1 still sends its own Host.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[HOST, "localhost"])

    routers = (projects, steps, deck, archive, discovery, audit, squad, core, events)
    for router in (r.router for r in routers):
        app.include_router(router)
    app.include_router(core.github_router)

    def error(status: int) -> Callable[[Request, Exception], Awaitable[Response]]:
        async def handle(_: Request, exc: Exception) -> Response:
            return JSONResponse({"detail": redact.redact(str(exc))}, status_code=status)

        return handle

    # Handlers match the most specific class, so MissingKey (fixable in Core access) gets 409.
    for exc, status in (
        (NotFound, 404),
        (Conflict, 409),
        (InvalidTransition, 409),
        (MissingKey, 409),
        (LLMError, 502),
    ):
        app.add_exception_handler(exc, error(status))

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/session")
    def session() -> dict[str, str]:
        return {"token": token}

    return app
