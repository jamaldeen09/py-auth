"""
Core exception classes for py-auth.
"""


class PyAuthError(Exception):
    """Base exception for all py-auth errors."""

    pass


class DuplicateEntryError(PyAuthError):
    """Raised when a unique constraint or duplicate entry violation occurs (HTTP 409)."""

    pass


class ForeignKeyViolationError(PyAuthError):
    """Raised when a foreign key constraint violation occurs (HTTP 400)."""

    pass


class RecordNotFoundError(PyAuthError):
    """Raised when a requested database record cannot be found (HTTP 404)."""

    pass


class AdapterError(PyAuthError):
    """Raised when an adapter or database engine is misconfigured or fails setup (HTTP 500)."""

    pass


class ConfigurationError(PyAuthError):
    """Raised when the core library is misconfigured during setup (HTTP 500)."""

    pass


__all__ = [
    "PyAuthError",
    "DuplicateEntryError",
    "ForeignKeyViolationError",
    "RecordNotFoundError",
    "AdapterError",
    "ConfigurationError",
]