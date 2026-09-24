

from py_auth._utils import merge_cookie_config
from py_auth.schemas import (
    CookieOptionsInput,
    CookieConfigInput,
    PyAuthCookiesInput,
)


def test_merge_cookie_config_returns_defaults_when_none():
    """Test that merge_cookie_config returns default cookie configurations when no user config is provided.

    When called without arguments, the function should return all cookies with their
    predefined secure defaults including proper names, security flags, and expiration times.
    """
    cookies = merge_cookie_config()

    assert cookies.session_token.name == "__Host-py_auth_session"
    assert cookies.session_token.options.http_only is True
    assert cookies.session_token.options.max_age == 30 * 24 * 60 * 60

    assert cookies.csrf_token.name == "py_auth_csrf"
    assert cookies.csrf_token.options.http_only is False
    assert cookies.csrf_token.options.max_age == 60 * 60

    assert cookies.state.name == "__Secure-py_auth.state"
    assert cookies.pkce_code_verifier.name == (
        "__Secure-py_auth.pkce.code_verifier"
    )
    assert cookies.nonce.name == "__Secure-py_auth.nonce"


def test_merge_cookie_config_preserves_defaults_for_unspecified_values():
    """Test that when a user overrides specific cookie options, unspecified values retain their secure defaults.

    This ensures that partial configuration changes don't accidentally disable security features
    or break functionality by preserving default values for any properties not explicitly set.
    """
    user_config = PyAuthCookiesInput(
        session_token=CookieConfigInput(
            options=CookieOptionsInput(
                max_age=3600,
            )
        )
    )

    cookies = merge_cookie_config(user_config)

    session_cookie = cookies.session_token

    assert session_cookie.options.max_age == 3600

    assert session_cookie.name == "__Host-py_auth_session"
    assert session_cookie.options.http_only is True
    assert session_cookie.options.secure is True
    assert session_cookie.options.same_site == "lax"
    assert session_cookie.options.path == "/"


def test_merge_cookie_config_overrides_cookie_name():
    """Test that users can override the default cookie names with custom values.

    This allows applications to customize cookie names to match their domain or
    naming conventions while maintaining all other default security settings.
    """
    user_config = PyAuthCookiesInput(
        session_token=CookieConfigInput(
            name="custom_session",
        )
    )

    cookies = merge_cookie_config(user_config)

    assert cookies.session_token.name == "custom_session"
    assert cookies.csrf_token.name == "py_auth_csrf"


def test_merge_cookie_config_overrides_multiple_options():
    """Test that users can override multiple cookie security options simultaneously.

    This verifies that when multiple properties are customized, all specified changes
    take effect while unspecified properties retain their default values.
    """
    user_config = PyAuthCookiesInput(
        csrf_token=CookieConfigInput(
            options=CookieOptionsInput(
                http_only=True,
                secure=False,
                max_age=1800,
            )
        )
    )

    cookies = merge_cookie_config(user_config)

    csrf_cookie = cookies.csrf_token

    assert csrf_cookie.options.http_only is True
    assert csrf_cookie.options.secure is False
    assert csrf_cookie.options.max_age == 1800
    assert csrf_cookie.options.same_site == "lax"
    assert csrf_cookie.options.path == "/"


def test_merge_cookie_config_supports_overrides_for_all_cookie_types():
    """Test that cookie name overrides work for all cookie types in the configuration.

    This ensures that users can customize names for session tokens, CSRF tokens, OAuth state,
    PKCE code verifiers, and nonces simultaneously, covering the full range of authentication cookies.
    """
    user_config = PyAuthCookiesInput(
        session_token=CookieConfigInput(name="custom_session"),
        csrf_token=CookieConfigInput(name="custom_csrf"),
        state=CookieConfigInput(name="custom_state"),
        pkce_code_verifier=CookieConfigInput(name="custom_pkce"),
        nonce=CookieConfigInput(name="custom_nonce"),
    )

    cookies = merge_cookie_config(user_config)

    assert cookies.session_token.name == "custom_session"
    assert cookies.csrf_token.name == "custom_csrf"
    assert cookies.state.name == "custom_state"
    assert cookies.pkce_code_verifier.name == "custom_pkce"
    assert cookies.nonce.name == "custom_nonce"