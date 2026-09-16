import hashlib, secrets, logging

from typing import Any

from .schemas import PyAuthCookiesInput, AuthError, AuthResult, CookieConfig, CookieOptions, PyAuthCookies

def generate_token(num_bytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """Produce a SHA-256 hash digest of a given token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_logger():
    """Retrieve the centralized namespaced logger for the py-auth library.

    Using a dedicated namespace ('py_auth') allows consuming applications
    to configure logging levels, formats, or handlers specifically for this
    package without polluting or altering the main application's logs.
    """
    return logging.getLogger("py_auth")

def get_auth_result(data: Any | None = None, error: AuthError | None = None) -> AuthResult:
    """Construct a standardized py-auth response."""
    return {"data": data, "error": error}


_DEFAULTS = PyAuthCookies(
    session_token=CookieConfig(
        name="__Host-py_auth_session",
        options=CookieOptions(
            http_only=True,
            secure=True,
            same_site="lax",
            path="/",
            expires=None,
            domain=None,
            max_age=30 * 24 * 60 * 60,
        )
    ),

    csrf_token=CookieConfig(
        name="py_auth_csrf",
        options=CookieOptions(
            http_only=False,
            secure=True,
            same_site="lax",
            path="/",
            expires=None,
            domain=None,
            max_age=60 * 60,
        ),
    ),
)

def merge_cookie_config(
    user_config: PyAuthCookiesInput | None = None,
) -> PyAuthCookies:
    """Merge user cookie options with the default cookie configuration."""

    session_token = _DEFAULTS.session_token
    csrf_token = _DEFAULTS.csrf_token

    if user_config is not None:
        if user_config.session_token is not None:
            session_token = CookieConfig(
                name=(
                    user_config.session_token.name
                    if user_config.session_token.name is not None
                    else _DEFAULTS.session_token.name
                ),
                options=CookieOptions(
                    **_DEFAULTS.session_token.options.model_dump(),
                    **user_config.session_token.options.model_dump(
                        exclude_none=True
                    )
                    if user_config.session_token.options is not None
                    else {},
                ),
            )

        if user_config.csrf_token is not None:
            csrf_token = CookieConfig(
                name=(
                    user_config.csrf_token.name
                    if user_config.csrf_token.name is not None
                    else _DEFAULTS.csrf_token.name
                ),
                options=CookieOptions(
                    **_DEFAULTS.csrf_token.options.model_dump(),
                    **user_config.csrf_token.options.model_dump(
                        exclude_none=True
                    )
                    if user_config.csrf_token.options is not None
                    else {},
                ),
            )

    return PyAuthCookies(session_token=session_token,csrf_token=csrf_token)