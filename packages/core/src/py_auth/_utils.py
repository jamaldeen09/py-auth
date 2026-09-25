import hashlib, secrets, logging

from typing import Any, Dict

from .schemas import (
    AuthError, 
    AuthResult, 
    CookieConfigInput, 
    PyAuthCookiesInput, 
    CookieConfig, 
    CookieOptions, 
    PyAuthCookies
)
from .cookies import COOKIES

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

    
def merge(
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
        session_token=merge(
            COOKIES.session_token,
            user_config.session_token if user_config else None,
        ),
        csrf_token=merge(
            COOKIES.csrf_token,
            user_config.csrf_token if user_config else None,
        ),
        state=merge(
            COOKIES.state,
            user_config.state if user_config else None,
        ),
        pkce_code_verifier=merge(
            COOKIES.pkce_code_verifier,
            user_config.pkce_code_verifier if user_config else None,
        ),
        nonce=merge(
            COOKIES.nonce,
            user_config.nonce if user_config else None,
        ),
    )

def generate_code_verifier () -> str:
    """Generate a cryptographically secure PKCE code verifier for OAuth 2.0 authorization code flow.

    The code verifier is a random string used in the PKCE (Proof Key for Code Exchange) extension
    to prevent authorization code interception attacks. It's combined with a code challenge to
    securely bind the authorization request to the token request.
    """
    return generate_token(num_bytes=46)

def generate_nonce () -> str:
    """Generate a cryptographically secure nonce for OpenID Connect authentication.

    A nonce is a random value used to mitigate replay attacks in OIDC. It's sent in the
    authentication request and returned in the ID token, allowing verification that the
    token response corresponds to the original request.
    """
    return generate_token(num_bytes=32)

def generate_session_token () -> str:
    """Generate a cryptographically secure session token for user authentication sessions.

    Session tokens are used to maintain authenticated user sessions across requests.
    They're stored in cookies and validated on each request to verify the user's
    authentication status.
    """
    return generate_token(num_bytes=48)

def generate_csrf_token () -> str:
    """Generate a cryptographically secure CSRF token for Cross-Site Request Forgery protection.

    CSRF tokens are used to prevent CSRF attacks by implementing the double-submit pattern.
    The token is stored in a cookie and included in form submissions or request headers,
    allowing the server to verify that requests originate from the legitimate application.
    """
    return generate_token(num_bytes=32)