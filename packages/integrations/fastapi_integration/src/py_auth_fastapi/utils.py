import logging

from py_auth.schemas import AuthError
from fastapi.exceptions import HTTPException
from typing import NoReturn

def raise_auth_exception(error: AuthError) -> NoReturn:
    """Helper to cleanly translate py-auth errors into FastAPI HTTPExceptions."""
    status_code = error.get("status_code", 500)
    message = error.get("message", "Something went wrong.")
    code = error.get("code", "AUTH_ERROR")
    details = error.get("details", {})

    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "message": message,
            "error": {"status_code": status_code, "code": code, "details": details},
        },
    )


def get_logger():
    """Retrieve the centralized namespaced logger for the py-auth library.

    Using a dedicated namespace ('py_auth') allows consuming applications
    to configure logging levels, formats, or handlers specifically for this
    package without polluting or altering the main application's logs.
    """
    return logging.getLogger("py_auth.fastapi")