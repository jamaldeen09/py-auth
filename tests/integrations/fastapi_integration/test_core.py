import pytest

from unittest.mock import MagicMock
from fastapi import Request, Response
from py_auth import PyAuth
from py_auth.schemas import CookieConfig, CookieOptions, PyAuthCookies
from py_auth_fastapi.core import PyAuthFastAPI


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


def test_py_auth_fastapi_initialization_with_defaults(mock_auth):
    """Test that PyAuthFastAPI initializes with default parameters."""
    router = PyAuthFastAPI(auth=mock_auth)
    
    assert router.auth is mock_auth
    assert router.prefix == "/auth"
    assert router.tags == ["Authentication"]


def test_py_auth_fastapi_initialization_with_custom_params(mock_auth):
    """Test that PyAuthFastAPI initializes with custom parameters."""
    router = PyAuthFastAPI(
        auth=mock_auth,
        prefix="/custom-auth",
        tags=["CustomAuth"]
    )
    
    assert router.auth is mock_auth
    assert router.prefix == "/custom-auth"
    assert router.tags == ["CustomAuth"]


def test_set_auth_cookie_applies_all_configurations(py_auth_fastapi):
    """Test that _set_auth_cookie correctly applies all cookie configuration options."""
    response = MagicMock(spec=Response)
    cookie_config = CookieConfig(
        name="test_cookie",
        options=CookieOptions(
            http_only=True,
            secure=True,
            same_site="strict",
            path="/api",
            domain="example.com",
            max_age=3600,
            expires=None
        )
    )
    
    py_auth_fastapi._set_auth_cookie(response, cookie_config, "test_value")
    
    response.set_cookie.assert_called_once_with(
        key="test_cookie",
        value="test_value",
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api",
        domain="example.com",
        max_age=3600,
        expires=None
    )


def test_clear_auth_cookie_uses_correct_parameters(py_auth_fastapi):
    """Test that _clear_auth_cookie uses the correct parameters for cookie deletion."""
    response = MagicMock(spec=Response)
    cookie_config = CookieConfig(
        name="test_cookie",
        options=CookieOptions(
            http_only=True,
            secure=True,
            same_site="strict",
            path="/api",
            domain="example.com",
            max_age=3600
        )
    )
    
    py_auth_fastapi._clear_auth_cookie(response, cookie_config)
    
    response.delete_cookie.assert_called_once_with(
        key="test_cookie",
        path="/api",
        domain="example.com",
        secure=True,
        httponly=True,
        samesite="strict"
    )


@pytest.mark.asyncio
async def test_verify_csrf_dependency_success(py_auth_fastapi):
    """Test that verify_csrf dependency passes when CSRF tokens match."""
    py_auth_fastapi.auth.verify_csrf_double_submit.return_value = {"error": None}
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "valid_token"
    request.headers.get.return_value = "valid_token"
    
    dependency = py_auth_fastapi.verify_csrf()
    result = await dependency(request)
    
    assert result is True
    py_auth_fastapi.auth.verify_csrf_double_submit.assert_called_once_with("valid_token", "valid_token")


@pytest.mark.asyncio
async def test_verify_csrf_dependency_raises_on_error(py_auth_fastapi):
    """Test that verify_csrf dependency raises HTTPException on CSRF validation failure."""
    
    error = {
        "code": "InvalidCSRF",
        "status_code": 403,
        "message": "CSRF validation failed"
    }
    py_auth_fastapi.auth.verify_csrf_double_submit.return_value = {"error": error}
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "cookie_token"
    request.headers.get.return_value = "header_token"
    
    dependency = py_auth_fastapi.verify_csrf()
    
    with pytest.raises(Exception): 
        await dependency(request)
    
    py_auth_fastapi.auth.verify_csrf_double_submit.assert_called_once_with("cookie_token", "header_token")


@pytest.mark.asyncio
async def test_verify_csrf_dependency_handles_missing_tokens(py_auth_fastapi):
    """Test that verify_csrf dependency handles missing cookie and header tokens."""
    py_auth_fastapi.auth.verify_csrf_double_submit.return_value = {"error": None}
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = ""
    request.headers.get.return_value = ""
    
    dependency = py_auth_fastapi.verify_csrf()
    result = await dependency(request)
    
    assert result is True
    py_auth_fastapi.auth.verify_csrf_double_submit.assert_called_once_with("", "")


@pytest.mark.asyncio
async def test_get_current_session_dependency_success(py_auth_fastapi):
    """Test that get_current_session dependency returns session data on successful validation."""
    py_auth_fastapi.auth.verify_session.return_value = {
        "error": None,
        "data": {"session": {"id": "session_123", "user_id": "user_456"}}
    }
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "valid_session_token"
    
    dependency = py_auth_fastapi.get_current_session()
    result = await dependency(request)
    
    assert result == {"id": "session_123", "user_id": "user_456"}
    py_auth_fastapi.auth.verify_session.assert_called_once_with("valid_session_token")


@pytest.mark.asyncio
async def test_get_current_session_dependency_with_csrf_verification(py_auth_fastapi):
    """Test that get_current_session dependency is created with CSRF verification when requested."""
    dependency = py_auth_fastapi.get_current_session(add_csrf_verification=True)
    
    assert callable(dependency)
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "valid_session_token"
    
    py_auth_fastapi.auth.verify_session.return_value = {
        "error": None,
        "data": {"session": {"id": "session_123"}}
    }
    
    result = await dependency(request)
    
    assert result == {"id": "session_123"}
    py_auth_fastapi.auth.verify_session.assert_called_once_with("valid_session_token")


@pytest.mark.asyncio
async def test_get_current_session_dependency_raises_on_session_error(py_auth_fastapi):
    """Test that get_current_session dependency raises HTTPException on session validation failure."""
    error = {
        "code": "InvalidSession",
        "status_code": 401,
        "message": "Session is invalid"
    }
    py_auth_fastapi.auth.verify_session.return_value = {"error": error}
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "invalid_token"
    dependency = py_auth_fastapi.get_current_session()
    
    with pytest.raises(Exception): 
        await dependency(request)
    
    py_auth_fastapi.auth.verify_session.assert_called_once_with("invalid_token")


@pytest.mark.asyncio
async def test_get_current_session_dependency_raises_on_invalid_data_type(py_auth_fastapi):
    """Test that get_current_session dependency raises HTTPException when data is not a dictionary."""
    py_auth_fastapi.auth.verify_session.return_value = {
        "error": None,
        "data": "invalid_data_type" 
    }
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "valid_token"
    
    dependency = py_auth_fastapi.get_current_session()
    
    with pytest.raises(Exception):
        await dependency(request)


@pytest.mark.asyncio
async def test_get_current_session_dependency_raises_on_missing_data(py_auth_fastapi):
    """Test that get_current_session dependency raises HTTPException when data is missing."""
    py_auth_fastapi.auth.verify_session.return_value = {
        "error": None,
        "data": None
    }
    
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "valid_token"
    
    dependency = py_auth_fastapi.get_current_session()
    
    with pytest.raises(Exception): 
        await dependency(request)


def test_py_auth_fastapi_registers_routes(mock_auth):
    """Test that PyAuthFastAPI registers all expected routes during initialization."""
    router = PyAuthFastAPI(auth=mock_auth)
    route_paths = [route.path for route in router.routes]
    
    expected_routes = [
        "/auth/csrf",
        "/auth/signin/credentials", 
        "/auth/signout",
        "/auth/session",
        "/auth/signin/google",
        "/auth/google/callback"
    ]
    
    for expected_route in expected_routes:
        assert expected_route in route_paths, f"Expected route {expected_route} not found"


def test_py_auth_fastapi_inherits_from_api_router(mock_auth):
    """Test that PyAuthFastAPI properly inherits from FastAPI's APIRouter."""
    router = PyAuthFastAPI(auth=mock_auth)
    
    assert hasattr(router, 'get')
    assert hasattr(router, 'post')
    assert hasattr(router, 'routes')
    assert hasattr(router, 'prefix')
    assert hasattr(router, 'tags')