from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from hmac import compare_digest
from secrets import token_urlsafe

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend import db, redact

HOST = "127.0.0.1"  # never 0.0.0.0 (SECURITY.md section 8)
PORT = 8000
UI_ORIGIN = "http://127.0.0.1:5173"
TOKEN_HEADER = "X-VCPG-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    redact.install()
    db.connect().close()  # apply migrations before the first request
    yield


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

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/session")
    def session() -> dict[str, str]:
        return {"token": token}

    return app
