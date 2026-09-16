"""Tests for py_auth.core — PyAuth session lifecycle engine."""

from __future__ import annotations

import datetime
from typing import Any, Dict

import pytest
from pydantic import BaseModel

from py_auth import PyAuth
from py_auth.providers.credentials import CredentialsProvider
from py_auth.utils import hash_token

from conftest import CollisionAdapter, FakeAdapter


class LoginBody(BaseModel):
    email: str
    password: str


async def authorize_ok(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    return {"id": "user-0", "email": payload["email"]}


async def authorize_missing_id(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    return {"email": payload["email"]}


async def authorize_none(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    return None


def make_auth(adapter: FakeAdapter, authorize=authorize_ok) -> PyAuth:
    provider = CredentialsProvider(model=LoginBody, authorize=authorize)
    return PyAuth(adapter=adapter, providers=[provider])


async def test_signin_creates_hashed_session_and_returns_tokens() -> None:
    adapter = FakeAdapter()
    auth = make_auth(adapter)

    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )

    assert result["error"] is None
    data = result["data"]
    session_token: str = data["session_token"]
    csrf_token: str = data["csrf_token"]
    assert data["user"] == {"id": "user-0", "email": "a@b.io"}
    assert len(session_token) == 64  # 48 bytes -> 64 url-safe chars
    assert len(csrf_token) == 43  # 32 bytes -> 43 url-safe chars

    # Only the SHA-256 digest is persisted — never the raw token.
    stored = next(iter(adapter.sessions.values()))
    assert stored["session_token_hash"] == hash_token(session_token)
    assert session_token not in adapter.sessions


async def test_signin_retries_on_hash_collision_and_returns_final_token() -> None:
    adapter = CollisionAdapter(num_collisions=2)
    auth = make_auth(adapter)

    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )

    assert result["error"] is None
    assert adapter.create_calls == 3
    # All three attempts used a distinct session token.
    stored = next(iter(adapter.sessions.values()))
    assert stored["session_token_hash"] == hash_token(result["data"]["session_token"])


async def test_signin_exhausts_retries_and_fails_cleanly() -> None:
    adapter = CollisionAdapter(num_collisions=99)
    auth = make_auth(adapter)

    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )

    assert result["data"] is None
    assert result["error"]["code"] == "SessionCreationFailed"
    assert result["error"]["status_code"] == 500


async def test_signin_without_credentials_provider() -> None:
    auth = PyAuth(adapter=FakeAdapter())

    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )

    assert result["error"]["code"] == "InternalServerError"


async def test_signin_rejected_credentials() -> None:
    auth = make_auth(FakeAdapter(), authorize=authorize_none)
    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "nope"}
    )
    assert result["error"]["code"] == "CredentialsSignIn"
    assert adapter_has_no_sessions(auth)


def adapter_has_no_sessions(auth: PyAuth) -> bool:
    return len(auth.adapter.sessions) == 0


async def test_signin_invalid_user_id_type() -> None:
    async def authorize_bad(payload: Dict[str, Any]) -> Dict[str, Any] | None:
        return {"id": 42, "email": payload["email"]}

    auth = make_auth(FakeAdapter(), authorize=authorize_bad)
    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    assert result["error"]["code"] == "InternalServerError"


async def test_signin_foreign_key_violation() -> None:
    class FkViolationAdapter(FakeAdapter):
        async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any] | None:
            from py_auth.exceptions import ForeignKeyViolationError

            raise ForeignKeyViolationError("violates foreign key constraint")

    auth = make_auth(FkViolationAdapter())
    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    assert result["error"]["code"] == "ForeignKeyViolation"
    assert result["error"]["status_code"] == 400


async def test_signin_unexpected_adapter_error_is_500() -> None:
    class BrokenAdapter(FakeAdapter):
        async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any] | None:
            raise RuntimeError("db down")

    auth = make_auth(BrokenAdapter())
    result = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    assert result["error"]["code"] == "InternalServerError"
    assert result["error"]["status_code"] == 500


async def test_verify_session_success() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    token = signin["data"]["session_token"]
    csrf = signin["data"]["csrf_token"]

    result = await auth.verify_session(token, csrf)
    assert result["error"] is None
    assert result["data"]["session"]["user_id"] == "user-0"


async def test_verify_session_missing_tokens() -> None:
    auth = make_auth(FakeAdapter())
    assert (await auth.verify_session("", "x"))["error"]["code"] == "MissingSessionToken"
    assert (await auth.verify_session("x", ""))["error"]["code"] == "MissingCsrfToken"


async def test_verify_session_unknown_token() -> None:
    auth = make_auth(FakeAdapter())
    result = await auth.verify_session("nope", "nope")
    assert result["error"]["code"] == "InvalidSession"
    assert result["error"]["status_code"] == 401


async def test_verify_session_csrf_mismatch() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    token = signin["data"]["session_token"]

    result = await auth.verify_session(token, "wrong-csrf")
    assert result["error"]["code"] == "InvalidCsrfToken"
    assert result["error"]["status_code"] == 403


async def test_verify_session_expired_deletes_session() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    token = signin["data"]["session_token"]
    csrf = signin["data"]["csrf_token"]
    session_id = next(iter(auth.adapter.sessions))

    # Backdate the expiry into the past.
    await auth.adapter.update_session(
        session_id,
        {"expires": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)},
    )

    result = await auth.verify_session(token, csrf)
    assert result["error"]["code"] == "SessionExpired"
    assert result["error"]["status_code"] == 401
    # The dead session is evicted.
    assert auth.adapter.sessions == {}
    assert hash_token(token) in auth.adapter.deleted_by_hash


async def test_verify_session_malformed_expires() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    token = signin["data"]["session_token"]
    session_id = next(iter(auth.adapter.sessions))
    await auth.adapter.update_session(session_id, {"expires": "2026-01-01"})

    result = await auth.verify_session(token, "irrelevant")
    assert result["error"]["code"] == "InternalServerError"


async def test_verify_session_missing_csrf_field() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    token = signin["data"]["session_token"]
    session_id = next(iter(auth.adapter.sessions))
    await auth.adapter.update_session(session_id, {"csrf_token": None})

    result = await auth.verify_session(token, "irrelevant")
    assert result["error"]["code"] == "InternalServerError"


async def test_verify_session_adapter_error_is_internal_500() -> None:
    class ExplodingAdapter(FakeAdapter):
        async def get_session_by_session_token_hash(
            self, session_token_hash: str
        ) -> Dict[str, Any] | None:
            raise RuntimeError("db unreachable")

    auth = make_auth(ExplodingAdapter())
    result = await auth.verify_session("t", "c")
    assert result["error"]["code"] == "InternalServerError"
    assert result["error"]["status_code"] == 500


async def test_signout_deletes_session() -> None:
    auth = make_auth(FakeAdapter())
    await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    session_id = next(iter(auth.adapter.sessions))

    result = await auth.signout(session_id)
    assert result["error"] is None
    assert result["data"] == {"signed_out": True}
    assert auth.adapter.sessions == {}


async def test_signout_missing_session_is_idempotent() -> None:
    auth = make_auth(FakeAdapter())
    result = await auth.signout("does-not-exist")
    assert result["error"] is None
    assert result["data"] == {"signed_out": True}


async def test_rotate_csrf_returns_new_token_and_persists() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    old_csrf = signin["data"]["csrf_token"]
    session_id = next(iter(auth.adapter.sessions))

    result = await auth.rotate_csrf(session_id)
    assert result["error"] is None
    new_csrf = result["data"]["csrf_token"]
    assert new_csrf != old_csrf
    assert new_csrf == auth.adapter.sessions[session_id]["csrf_token"]


async def test_rotate_csrf_can_verify_with_new_token() -> None:
    auth = make_auth(FakeAdapter())
    signin = await auth.signin_with_credentials(
        {"email": "a@b.io", "password": "hunter2"}
    )
    token = signin["data"]["session_token"]
    session_id = next(iter(auth.adapter.sessions))
    new_csrf = (await auth.rotate_csrf(session_id))["data"]["csrf_token"]

    assert (await auth.verify_session(token, new_csrf))["error"] is None
    assert (await auth.verify_session(token, signin["data"]["csrf_token"]))[
        "error"
    ]["code"] == "InvalidCsrfToken"


async def test_rotate_csrf_missing_session() -> None:
    auth = make_auth(FakeAdapter())
    result = await auth.rotate_csrf("ghost-session")
    assert result["error"]["code"] == "SessionNotFound"
    assert result["error"]["status_code"] == 404


async def test_adapter_protocol_enforced_at_construction() -> None:
    from py_auth.exceptions import ConfigurationError

    class NotAnAdapter:
        pass

    with pytest.raises(ConfigurationError):
        PyAuth(adapter=NotAnAdapter())