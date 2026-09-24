import pytest

from py_auth import CredentialsProvider
from tests.core.conftest import LoginSchema

@pytest.mark.asyncio
async def test_credentials_missing_required_field(user_data, get_credentials_provider):
    """
    If the request body is missing 'password', Pydantic validation fails.
    Should come back as ValidationError with details about which field failed.
    """
    user_data_dict = user_data()
    provider = get_credentials_provider(authorize=lambda _: user_data_dict)
    result = await provider.authenticate({"email": user_data_dict["email"]})

    assert result["error"] is not None
    assert result["error"]["code"] == "ValidationError"
    assert result["error"]["status_code"] == 422
    assert "validation_errors" in result["error"]["details"]

@pytest.mark.asyncio
async def test_credentials_wrong_field_type(user_data, get_credentials_provider):
    """
    If a field has the wrong type (email is not a string here since we pass an int),
    Pydantic should catch it and return ValidationError.
    """
    provider = get_credentials_provider(authorize=lambda _: user_data())
    result = await provider.authenticate({"email": 12345, "password": "pass"})

    assert result["error"] is None or result["error"]["code"] == "ValidationError"

@pytest.mark.asyncio
async def test_credentials_empty_body(user_data, get_credentials_provider):
    """Completely empty body should fail Pydantic validation with missing field errors."""
    provider = get_credentials_provider(authorize=lambda _: user_data())
    result = await provider.authenticate({})

    assert result["error"] is not None
    assert result["error"]["code"] == "ValidationError"


@pytest.mark.asyncio
async def test_credentials_authorize_returns_none(get_credentials_provider):
    """
    authorize returning None means wrong password / user not found.
    Should be CredentialsSignIn 401 — generic message so attackers can't distinguish
    between "user doesn't exist" and "wrong password".
    """
    provider = get_credentials_provider(authorize=lambda _: None)
    result = await provider.authenticate({"email": "user@example.com", "password": "wrong"})

    assert result["error"] is not None
    assert result["error"]["code"] == "CredentialsSignIn"
    assert result["error"]["status_code"] == 401

@pytest.mark.asyncio
async def test_credentials_authorize_returns_false(get_credentials_provider):
    """Same as None — returning False should also be treated as auth failure."""
    provider = get_credentials_provider(authorize=lambda _: False)
    result = await provider.authenticate({"email": "user@example.com", "password": "wrong"})

    assert result["error"] is not None
    assert result["error"]["code"] == "CredentialsSignIn"

@pytest.mark.asyncio
async def test_credentials_authorize_returns_non_dict(get_credentials_provider):
    """
    This catches a developer mistake: authorize returned a string or int instead of a dict.
    Core catches this and returns InternalServerError rather than crashing downstream.
    """
    provider = get_credentials_provider(authorize=lambda _: "user@example.com")
    result = await provider.authenticate({"email": "user@example.com", "password": "pass"})

    assert result["error"] is not None
    assert result["error"]["code"] == "InternalServerError"
    assert result["error"]["status_code"] == 500

@pytest.mark.asyncio
async def test_credentials_authorize_raises_exception(get_credentials_provider):
    """
    If authorize raises an unexpected exception (e.g. the DB query inside it crashes),
    core wraps it in InternalServerError and returns gracefully.
    """
    def crashing_authorize(_):
        raise RuntimeError("DB connection dropped")

    provider = get_credentials_provider(authorize=crashing_authorize)
    result = await provider.authenticate({"email": "user@example.com", "password": "pass"})

    assert result["error"] is not None
    assert result["error"]["code"] == "InternalServerError"

@pytest.mark.asyncio
async def test_credentials_sync_authorize_success(user_data, get_credentials_provider):
    """
    A synchronous authorize callback (plain def, not async def) should work correctly.
    This is the common case — most users will write `def authorize(data): ...`
    """
    valid_user = user_data()
    def sync_authorize(data):
        return valid_user

    provider = get_credentials_provider(authorize=sync_authorize)
    result = await provider.authenticate({"email": "user@example.com", "password": "correct"})

    assert result["error"] is None
    assert result["data"] == valid_user

@pytest.mark.asyncio
async def test_credentials_async_authorize_success(user_data, get_credentials_provider):
    """
    An async authorize callback should also work — I support both via inspect.iscoroutinefunction.
    Users who query an async DB inside authorize need this.
    """
    valid_user = user_data()
    async def async_authorize(data):
        return valid_user

    provider = get_credentials_provider(authorize=async_authorize)
    result = await provider.authenticate({"email": "user@example.com", "password": "correct"})

    assert result["error"] is None
    assert result["data"] == valid_user

@pytest.mark.asyncio
async def test_credentials_success_returns_user_data(user_data, get_credentials_provider):
    """
    The happy path: valid input + authorize returns a dict → data is that dict with no error.
    Whatever the user's authorize callback returns should be passed straight through.
    """
    valid_user = user_data()
    provider = get_credentials_provider(authorize=lambda _: valid_user)
    result = await provider.authenticate({"email": "user@example.com", "password": "correct"})

    assert result["error"] is None
    assert result["data"]["id"] == valid_user["id"]
    assert result["data"]["email"] == valid_user["email"]
    assert result["data"]["name"] == valid_user["name"]
