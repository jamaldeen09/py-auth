
import pytest

from unittest.mock import AsyncMock
from py_auth import PyAuth
from pydantic import BaseModel

@pytest.fixture
def mock_adapter():
    """
    A fully mocked adapter.

    Every method is an AsyncMock by default, meaning calling
    `await mock_adapter.get_session_by_session_token_hash(...)` works
    but returns None unless I override the return value in the test.
    """
    adapter = AsyncMock()
    adapter.get_or_create_user_and_link_account = AsyncMock()
    adapter.create_user = AsyncMock()
    adapter.get_user_by_email = AsyncMock()
    adapter.get_user = AsyncMock()
    adapter.link_account = AsyncMock()
    adapter.unlink_account = AsyncMock()
    adapter.delete_user = AsyncMock()
    adapter.list_accounts_for_user = AsyncMock()
    adapter.list_sessions_for_user = AsyncMock()
    adapter.create_session = AsyncMock()
    adapter.get_session_by_session_token_hash = AsyncMock()
    adapter.delete_session_by_session_token_hash = AsyncMock()
    adapter.delete_session = AsyncMock()
    adapter.update_session = AsyncMock()
    return adapter

@pytest.fixture
def auth(mock_adapter):
    """
    A bare PyAuth instance wired to the mock adapter.
    I'll use this for most tests (verify_session, signout, CSRF).
    """
    return PyAuth(adapter=mock_adapter)

class LoginSchema(BaseModel):
    """Minimal login schema — just what I need to test credentials validation."""
    email: str
    password: str