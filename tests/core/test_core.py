import pytest

from datetime import datetime, timezone, timedelta
from py_auth._utils import hash_token


@pytest.mark.asyncio
async def test_verify_session_missing_token(auth):
    """
    Empty string token should be rejected immediately without even touching the adapter.
    The auth system must fail fast on obviously bad input.
    """
    result = await auth.verify_session("")
    assert result["error"] is not None
    assert result["error"]["code"] == "MissingSessionToken"
    assert result["error"]["status_code"] == 401

@pytest.mark.asyncio
async def test_verify_session_not_found(auth, mock_adapter):
    """
    When the adapter returns None for the token hash, the session doesn't exist.
    Should come back as InvalidSession — not a crash.
    """
    mock_adapter.get_session_by_session_token_hash.return_value = None

    result = await auth.verify_session("some_token")
    assert result["error"] is not None
    assert result["error"]["code"] == "InvalidSession"
    assert result["error"]["status_code"] == 401

@pytest.mark.asyncio
async def test_verify_session_valid(auth, mock_adapter):
    """
    A valid, non-expired session should return data (the session dict) with no error.
    The expires field must be in the future for this to work.
    """
    future_expiry = datetime.now(timezone.utc) + timedelta(days=7)
    mock_adapter.get_session_by_session_token_hash.return_value = {
        "id": "sess_123",
        "user_id": "usr_1",
        "session_token_hash": "abc123",
        "expires": future_expiry,
    }

    result = await auth.verify_session("valid_token")
    assert result["error"] is None
    assert result["data"]["session"]["id"] == "sess_123"

@pytest.mark.asyncio
async def test_verify_session_expired(auth, mock_adapter):
    """
    An expired session should be automatically deleted AND return SessionExpired error.

    This is important — if I forget to call delete_session_by_session_token_hash here,
    expired sessions pile up in the database forever. I'm asserting both things:
    1. The error code is correct
    2. The adapter's delete method was actually called
    """
    past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    mock_adapter.get_session_by_session_token_hash.return_value = {
        "id": "sess_old",
        "user_id": "usr_1",
        "session_token_hash": hash_token("expired_token"),
        "expires": past_expiry,
    }

    result = await auth.verify_session("expired_token")
    assert result["error"] is not None
    assert result["error"]["code"] == "SessionExpired"
    assert result["error"]["status_code"] == 401
    mock_adapter.delete_session_by_session_token_hash.assert_called_once()

@pytest.mark.asyncio
async def test_verify_session_adapter_crashes(auth, mock_adapter):
    """
    If the adapter unexpectedly raises an exception (e.g. DB connection dropped),
    core.py should catch it and return InternalServerError — not let it propagate
    and crash the FastAPI handler with a raw Python traceback.
    """
    mock_adapter.get_session_by_session_token_hash.side_effect = Exception("DB is down")

    result = await auth.verify_session("any_token")
    assert result["error"] is not None
    assert result["error"]["code"] == "InternalServerError"
    assert result["error"]["status_code"] == 500

@pytest.mark.asyncio
async def test_verify_session_invalid_expires_type(auth, mock_adapter):
    """
    If the adapter returns a session where 'expires' is not a datetime object (e.g. a
    string like "2026-01-01"), core.py must catch it and return InternalServerError.
    This defends against a misconfigured or buggy adapter.
    """
    mock_adapter.get_session_by_session_token_hash.return_value = {
        "id": "sess_bad",
        "user_id": "usr_1",
        "session_token_hash": "abc",
        "expires": "2026-01-01T00:00:00", 
    }

    result = await auth.verify_session("any_token")
    assert result["error"] is not None
    assert result["error"]["code"] == "InternalServerError"


@pytest.mark.asyncio
async def test_signout_success(auth, mock_adapter):
    """
    Signing out an existing session should return signed_out=True.
    The adapter's delete_session must be called with the correct session ID.
    """
    mock_adapter.delete_session.return_value = None

    result = await auth.signout("sess_123")
    assert result["error"] is None
    assert result["data"]["signed_out"] is True
    mock_adapter.delete_session.assert_called_once_with("sess_123")

@pytest.mark.asyncio
async def test_signout_adapter_crashes(auth, mock_adapter):
    """
    If delete_session blows up, signout should return InternalServerError.
    A crashed signout is bad UX — the user thinks they're logged out but they're not.
    """
    mock_adapter.delete_session.side_effect = Exception("unexpected failure")

    result = await auth.signout("sess_123")
    assert result["error"] is not None
    assert result["error"]["code"] == "InternalServerError"


def test_verify_csrf_valid(auth):
    """Matching cookie and submitted token should pass validation."""
    result = auth.verify_csrf_double_submit(
        cookie_csrf_token="abc123",
        submitted_csrf_token="abc123"
    )
    assert result["error"] is None
    assert result["data"]["validated"] is True

def test_verify_csrf_mismatch(auth):
    """
    If the submitted token doesn't match the cookie token, it's likely a CSRF attack.
    Must return 403 Forbidden — not 401, because the user IS authenticated, they're
    just submitting from the wrong origin.
    """
    result = auth.verify_csrf_double_submit(
        cookie_csrf_token="real_token",
        submitted_csrf_token="forged_token"
    )
    assert result["error"] is not None
    assert result["error"]["code"] == "InvalidCsrfToken"
    assert result["error"]["status_code"] == 403

def test_verify_csrf_missing_cookie_token(auth):
    """
    If the cookie token is missing (empty string), that means the cookie wasn't set
    or was already consumed. Should fail with MissingCsrfToken.
    """
    result = auth.verify_csrf_double_submit(
        cookie_csrf_token="",
        submitted_csrf_token="some_token"
    )
    assert result["error"] is not None
    assert result["error"]["code"] == "MissingCsrfToken"
    assert result["error"]["status_code"] == 401
