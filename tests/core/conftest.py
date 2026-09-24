
import pytest

from unittest.mock import AsyncMock
from py_auth import PyAuth
from .helpers import LoginSchema
from py_auth.providers import GoogleProvider, CredentialsProvider

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


@pytest.fixture
def google_provider():
    return GoogleProvider(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://example.com/callback",
    )

@pytest.fixture
def get_credentials_provider ():
    def credentials_provider (authorize):
        return CredentialsProvider(model=LoginSchema, authorize=authorize)
    
    return credentials_provider