"""
py-auth: Modular authentication primitives and provider framework for Python backends.
"""

from .base import BaseProvider
from .core import PyAuth
from .exceptions import (
    AdapterError,
    ConfigurationError,
    DuplicateEntryError,
    ForeignKeyViolationError,
    PyAuthError,
    RecordNotFoundError,
)
from .providers.credentials import CredentialsProvider
from .schemas import (
    AdapterContainer,
    AuthError,
    AuthResult,
    CookieConfig,
    CookieOptions,
    PyAuthAdapterProtocol,
    PyAuthCookiesInput,
)

__all__ = [
    "PyAuth",
    "BaseProvider",
    "CredentialsProvider",
    "PyAuthError",
    "DuplicateEntryError",
    "ForeignKeyViolationError",
    "RecordNotFoundError",
    "AdapterError",
    "ConfigurationError",
    "AuthError",
    "AuthResult",
    "CookieOptions",
    "CookieConfig",
    "PyAuthCookiesInput",
    "PyAuthAdapterProtocol",
    "AdapterContainer",
]

__version__ = "0.0.1"
