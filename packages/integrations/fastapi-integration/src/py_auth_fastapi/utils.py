from py_auth.schemas import AuthError
from fastapi.exceptions import HTTPException

def raise_auth_exception(error: AuthError):
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