import hashlib, secrets, logging

from typing import Any

from .schemas import PyAuthCookiesInput, AuthError, AuthResult, CookieConfig, CookieOptions, PyAuthCookies, CookieConfigInput

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

    state=CookieConfig(
        name="__Secure-py_auth.state",
        options=CookieOptions(
            http_only=True,
            secure=True,
            same_site="lax",
            path="/",
            domain=None,
            expires=None,
            max_age=900
        )
    ),

    pkce_code_verifier=CookieConfig(
        name="__Secure-py_auth.pkce.code_verifier",
        options=CookieOptions(
            http_only=True,
            secure=True,
            same_site="lax",
            path="/",
            domain=None,
            expires=None,
            max_age=900
        )
    ),

    nonce=CookieConfig(
        name="__Secure-py_auth.nonce",
        options=CookieOptions(
            http_only=True,
            secure=True,
            same_site="lax",
            path="/",
            domain=None,
            expires=None,
            max_age=900
        )
    )
)

def _merge_cookie_config(
    default: CookieConfig,
    override: CookieConfigInput | None,
) -> CookieConfig:
    """Merge a cookie configuration using the default and optional override."""
    if override is None:
        return default

    options = default.options.model_dump()

    if override.options is not None:
        options.update(
            override.options.model_dump(exclude_none=True)
        )

    return CookieConfig(
        name=(
            override.name
            if override.name is not None
            else default.name
        ),
        options=CookieOptions(**options),
    )

def merge_cookie_config(
    user_config: PyAuthCookiesInput | None = None,
) -> PyAuthCookies:
    """Merge the complete cookie configuration."""
    return PyAuthCookies(
        session_token=_merge_cookie_config(
            _DEFAULTS.session_token,
            user_config.session_token if user_config else None,
        ),
        csrf_token=_merge_cookie_config(
            _DEFAULTS.csrf_token,
            user_config.csrf_token if user_config else None,
        ),
        state=_merge_cookie_config(
            _DEFAULTS.state,
            user_config.state if user_config else None,
        ),
        pkce_code_verifier=_merge_cookie_config(
            _DEFAULTS.pkce_code_verifier,
            user_config.pkce_code_verifier if user_config else None,
        ),
        nonce=_merge_cookie_config(
            _DEFAULTS.nonce,
            user_config.nonce if user_config else None,
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