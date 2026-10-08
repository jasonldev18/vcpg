from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app import TOKEN_HEADER, UI_ORIGIN, create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()

    @app.post("/api/echo")
    def echo() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_state_changing_route_requires_session_token(client: TestClient) -> None:
    assert client.post("/api/echo").status_code == 403
    assert client.post("/api/echo", headers={TOKEN_HEADER: "guess"}).status_code == 403
    token = client.get("/api/session").json()["token"]
    assert client.post("/api/echo", headers={TOKEN_HEADER: token}).status_code == 200


def test_each_launch_gets_a_new_token() -> None:
    tokens = set()
    for _ in range(2):
        with TestClient(create_app(), base_url="http://127.0.0.1:8000") as c:
            tokens.add(c.get("/api/session").json()["token"])
    assert len(tokens) == 2


def test_cors_allows_only_the_ui_origin(client: TestClient) -> None:
    ok = client.get("/api/session", headers={"Origin": UI_ORIGIN})
    assert ok.headers["access-control-allow-origin"] == UI_ORIGIN
    other = client.get("/api/session", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_foreign_host_header_is_rejected(client: TestClient) -> None:
    assert client.get("/api/session", headers={"Host": "evil.example"}).status_code == 400
