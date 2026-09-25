import pytest

from fastapi.exceptions import HTTPException
from py_auth_fastapi.utils import raise_auth_exception, get_logger


def test_raise_auth_exception_with_full_error():
    """Test that raise_auth_exception correctly converts py-auth error to FastAPI HTTPException with all fields."""
    error = {
        "code": "TestError",
        "status_code": 400,
        "message": "Test error message",
        "details": {"field": "value"}
    }

    with pytest.raises(HTTPException) as exc_info:
        raise_auth_exception(error)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["success"] is False
    assert exc_info.value.detail["message"] == "Test error message"
    assert exc_info.value.detail["error"]["code"] == "TestError"
    assert exc_info.value.detail["error"]["status_code"] == 400
    assert exc_info.value.detail["error"]["details"] == {"field": "value"}

def test_raise_auth_exception_with_minimal_error():
    """Test that raise_auth_exception handles minimal error structure with defaults."""
    error = {
        "message": "Minimal error"
    }

    with pytest.raises(HTTPException) as exc_info:
        raise_auth_exception(error)

    assert exc_info.value.status_code == 500 
    assert exc_info.value.detail["success"] is False
    assert exc_info.value.detail["message"] == "Minimal error"
    assert exc_info.value.detail["error"]["code"] == "AUTH_ERROR"
    assert exc_info.value.detail["error"]["status_code"] == 500
    assert exc_info.value.detail["error"]["details"] == {} 

def test_raise_auth_exception_with_empty_error():
    """Test that raise_auth_exception handles empty error structure with all defaults."""
    error = {}

    with pytest.raises(HTTPException) as exc_info:
        raise_auth_exception(error)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["success"] is False
    assert exc_info.value.detail["message"] == "Something went wrong."
    assert exc_info.value.detail["error"]["code"] == "AUTH_ERROR"
    assert exc_info.value.detail["error"]["status_code"] == 500
    assert exc_info.value.detail["error"]["details"] == {}

def test_get_logger_returns_correct_namespace():
    """Test that get_logger returns a logger with the correct namespace."""
    logger = get_logger()
    assert logger.name == "py_auth.fastapi"

def test_get_logger_returns_same_instance():
    """Test that get_logger returns the same logger instance on multiple calls."""
    logger1 = get_logger()
    logger2 = get_logger()
    assert logger1 is logger2