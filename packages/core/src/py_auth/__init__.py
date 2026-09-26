"""Modular authentication primitives and provider framework for Python backends."""

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
from .providers.google import GoogleProvider
from .schemas import (
    AdapterContainer,
    AuthError,
    AuthResult,
    CookieConfig,
    CookieOptions,
    PyAuthAdapterProtocol,
    PyAuthCookiesInput,
    CookieConfigInput,
    PyAuthCookies,
    CookieOptionsInput,
)

__all__ = [
    "PyAuth",

    "PyAuthError",
    "DuplicateEntryError",
    "ForeignKeyViolationError",
    "RecordNotFoundError",
    "AdapterError",
    "ConfigurationError",

    "CredentialsProvider",
    "GoogleProvider",

    "AuthError",
    "AuthResult",
    "CookieOptions",
    "CookieConfig",
    "PyAuthCookiesInput",
    "PyAuthAdapterProtocol",
    "AdapterContainer",
    "CookieConfigInput",
    "PyAuthCookies",
    "CookieOptionsInput"
]

__version__ = "0.0.2"
