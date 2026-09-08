"""
Core exception classes for py-auth.
"""


class PyAuthError(Exception):
    """Base exception for all py-auth errors."""

    status_code: int = 500

    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class DuplicateEntryError(PyAuthError):
    """Raised when a unique constraint or duplicate entry violation occurs (HTTP 409)."""

    status_code: int = 409


class ForeignKeyViolationError(PyAuthError):
    """Raised when a foreign key constraint violation occurs (HTTP 400)."""

    status_code: int = 400


class RecordNotFoundError(PyAuthError):
    """Raised when a requested database record cannot be found (HTTP 404)."""

    status_code: int = 404


class AdapterError(PyAuthError):
    """Raised when an adapter or database engine is misconfigured or fails setup (HTTP 500)."""

    status_code: int = 500


class ConfigurationError(PyAuthError):
    """Raised when the core library is misconfigured during setup (HTTP 500)."""

    status_code: int = 500


__all__ = [
    "PyAuthError",
    "DuplicateEntryError",
    "ForeignKeyViolationError",
    "RecordNotFoundError",
    "AdapterError",
    "ConfigurationError",
]
