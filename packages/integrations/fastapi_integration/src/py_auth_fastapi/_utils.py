"""Utility functions for py-auth-fastapi"""

import logging

from py_auth.schemas import AuthError
from fastapi.exceptions import HTTPException
from typing import NoReturn

def raise_auth_exception(error: AuthError) -> NoReturn:
    """Translate py-auth errors into FastAPI HTTPExceptions with structured error responses."""
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
    """Retrieve the centralized namespaced logger for the py-auth FastAPI integration."""
    return logging.getLogger("py_auth.fastapi")