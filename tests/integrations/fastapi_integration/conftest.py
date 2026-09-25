import pytest

from unittest.mock import MagicMock
from py_auth.schemas import CookieConfig, CookieOptions, PyAuthCookies
from py_auth import PyAuth
from py_auth_fastapi import PyAuthFastAPI

@pytest.fixture
def mock_auth():
    """Create a mock PyAuth instance for testing."""
    auth = MagicMock(spec=PyAuth)
    auth.cookies = PyAuthCookies(
        session_token=CookieConfig(
            name="session_token",
            options=CookieOptions(
                http_only=True,
                secure=True,
                same_site="lax",
                path="/",
                max_age=30 * 24 * 60 * 60
            )
        ),
        csrf_token=CookieConfig(
            name="csrf_token",
            options=CookieOptions(
                http_only=False,
                secure=True,
                same_site="lax",
                path="/",
                max_age=60 * 60
            )
        ),
        state=CookieConfig(
            name="state",
            options=CookieOptions(
                http_only=True,
                secure=True,
                same_site="lax",
                path="/",
                max_age=900
            )
        ),
        pkce_code_verifier=CookieConfig(
            name="pkce_code_verifier",
            options=CookieOptions(
                http_only=True,
                secure=True,
                same_site="lax",
                path="/",
                max_age=900
            )
        ),
        nonce=CookieConfig(
            name="nonce",
            options=CookieOptions(
                http_only=True,
                secure=True,
                same_site="lax",
                path="/",
                max_age=900
            )
        )
    )
    auth._provider_map = {}
    return auth

@pytest.fixture
def py_auth_fastapi(mock_auth):
    """Create a PyAuthFastAPI instance for testing."""
    return PyAuthFastAPI(auth=mock_auth)