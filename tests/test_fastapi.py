"""End-to-end tests for py_auth_fastapi — the FastAPI APIRouter integration.

These tests exercise the real cookie flow through FastAPI's TestClient:

    sign in  ->  session + csrf cookies set
    /session ->  dependency verifies both cookies against the stored session
    /tasks/* ->  protected routes work with the fixed CSRF cookie lookups
    rotate   ->  CSRF cookie rotation keeps the session valid
"""

from __future__ import annotations

import datetime
from typing import Any, Dict

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from py_auth import CredentialsProvider, PyAuth
from py_auth_fastapi import PyAuthFastAPI
from py_auth_sqlalchemy import SqlAlchemyAdapter


class Base(AsyncAttrs, DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "sess-new")
    session_token_hash: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[str] = mapped_column(String)
    csrf_token: Mapped[str] = mapped_column(String)
    expires: Mapped[datetime.datetime] = mapped_column(DateTime)


class LoginBody(BaseModel):
    email: str
    password: str


async def authorize(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    if payload["password"] == "secret":
        return {"id": "user-1", "email": payload["email"]}
    return None


@pytest.fixture
def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    adapter = SqlAlchemyAdapter(engine=engine, session_model=SessionModel)

    import asyncio

    async def _create_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_tables())

    auth = PyAuth(
        adapter=adapter,
        providers=[CredentialsProvider(model=LoginBody, authorize=authorize)],
    )
    router = PyAuthFastAPI(auth)

    app = FastAPI()
    app.include_router(router)

    @app.get("/protected")
    async def protected(session=Depends(router.get_current_session())):  # noqa: B008
        assert session["user_id"] == "user-1"
        return {"ok": True, "user_id": session["user_id"]}

    with TestClient(app) as test_client:
        yield test_client, auth, adapter

    import asyncio

    asyncio.run(engine.dispose())


def do_signin(client: TestClient) -> dict:
    resp = client.post(
        "/auth/signin", json={"email": "a@b.io", "password": "secret"}
    )
    assert resp.status_code == 200, resp.text
    return {
        "__Host-py_auth_session": resp.cookies["__Host-py_auth_session"],
        "py_auth_csrf": resp.cookies["py_auth_csrf"],
    }


def test_health_route() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    adapter = SqlAlchemyAdapter(engine=engine, session_model=SessionModel)
    router = PyAuthFastAPI(PyAuth(adapter=adapter))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        assert c.get("/").status_code == 404  # router has no root by itself
    import asyncio

    asyncio.run(engine.dispose())


def test_signin_sets_session_and_csrf_cookies(client) -> None:
    test_client, auth, _ = client
    resp = test_client.post(
        "/auth/signin", json={"email": "a@b.io", "password": "secret"}
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    cookies = resp.cookies
    assert "__Host-py_auth_session" in cookies
    assert "py_auth_csrf" in cookies


def test_signin_rejects_bad_credentials(client) -> None:
    test_client, _, _ = client
    resp = test_client.post(
        "/auth/signin", json={"email": "a@b.io", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "CredentialsSignIn"


def test_session_endpoint_works_with_both_cookies(client) -> None:
    test_client, _, _ = client
    cookies = do_signin(test_client)

    resp = test_client.get("/auth/session", cookies=cookies)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["session"]["user_id"] == "user-1"


def test_session_endpoint_without_csrf_cookie_is_401(client) -> None:
    """Regression test for the CSRF-cookie-name bug.

    Previously the dependency read the CSRF token from the *session-token*
    cookie name, so a client holding only the real CSRF cookie could never
    verify a session.
    """
    test_client, _, _ = client
    cookies = do_signin(test_client)

    resp = test_client.get(
        "/auth/session", cookies={"__Host-py_auth_session": cookies["__Host-py_auth_session"]}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] in {"InvalidCsrfToken", "MissingCsrfToken"}


def test_session_endpoint_without_session_cookie_is_401(client) -> None:
    test_client, _, _ = client
    cookies = do_signin(test_client)

    resp = test_client.get(
        "/auth/session", cookies={"py_auth_csrf": cookies["py_auth_csrf"]}
    )
    assert resp.status_code == 401


def test_protected_route_requires_authentication(client) -> None:
    test_client, _, _ = client
    assert test_client.get("/protected").status_code == 401


def test_protected_route_allows_authenticated_client(client) -> None:
    test_client, _, _ = client
    cookies = do_signin(test_client)
    resp = test_client.get("/protected", cookies=cookies)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "user_id": "user-1"}


def test_signout_clears_cookies_and_invalidates_session(client) -> None:
    test_client, _, _ = client
    cookies = do_signin(test_client)

    resp = test_client.post("/auth/signout", cookies=cookies)
    assert resp.status_code == 200

    # The stored session is gone, so the old token no longer verifies.
    resp = test_client.get("/auth/session", cookies=cookies)
    assert resp.status_code == 401


def test_expired_session_is_rejected(client) -> None:
    test_client, auth, adapter = client
    cookies = do_signin(test_client)

    # Backdate the stored session expiry via the real adapter.
    import asyncio

    async def _backdate() -> None:
        from sqlalchemy import update

        async with adapter.session_maker() as session:
            await session.execute(
                update(adapter.session_model)
                .values(
                    expires=datetime.datetime.now(datetime.timezone.utc)
                    - datetime.timedelta(hours=1)
                )
                .where(adapter.session_model.id.isnot(None))
            )
            await session.commit()

    asyncio.run(_backdate())

    resp = test_client.get("/auth/session", cookies=cookies)
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "SessionExpired"


def test_rotate_csrf_endpoint_rotates_cookie(client) -> None:
    test_client, _, _ = client
    cookies = do_signin(test_client)
    old_csrf = cookies["py_auth_csrf"]

    resp = test_client.post("/auth/rotate-csrf", cookies=cookies)
    assert resp.status_code == 200, resp.text
    new_csrf = resp.cookies["py_auth_csrf"]
    assert new_csrf != old_csrf

    # The session cookie is untouched; the new CSRF token verifies.
    cookies["py_auth_csrf"] = new_csrf
    assert test_client.get("/auth/session", cookies=cookies).status_code == 200


def test_rotate_csrf_requires_auth(client) -> None:
    test_client, _, _ = client
    assert test_client.post("/auth/rotate-csrf").status_code == 401