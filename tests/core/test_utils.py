
from py_auth.utils import generate_token, hash_token, merge_cookie_config
from py_auth.schemas import PyAuthCookiesInput, CookieConfigInput, CookieOptionsInput


def test_generate_token_returns_string():
    """Should return a string — sanity check before anything else."""
    token = generate_token()
    assert isinstance(token, str)

def test_generate_token_default_is_not_empty():
    """An empty token would be catastrophic for session security."""
    token = generate_token()
    assert len(token) > 0

def test_generate_token_custom_length():
    """
    num_bytes controls entropy — a caller asking for more bytes should get a longer token.
    secrets.token_urlsafe returns ceil(num_bytes * 4/3) chars due to base64 encoding,
    so we just assert that a larger num_bytes gives a longer string.
    """
    short = generate_token(num_bytes=16)
    long = generate_token(num_bytes=64)
    assert len(long) > len(short)

def test_generate_token_is_unique():
    """
    Two consecutive calls must never return the same token.
    If they did, session tokens could collide and an attacker could guess valid sessions.
    """
    token_a = generate_token()
    token_b = generate_token()
    assert token_a != token_b


def test_hash_token_returns_string():
    """SHA-256 hex digest should always be a string."""
    result = hash_token("some_token")
    assert isinstance(result, str)

def test_hash_token_is_deterministic():
    """
    The same token must always produce the same hash.
    This matters because I store the hash in the DB and re-hash the cookie value
    to look up the session — if the hash changes, sessions would be invalid.
    """
    token = "my_session_token"
    assert hash_token(token) == hash_token(token)

def test_hash_token_different_inputs_give_different_hashes():
    """Two different tokens must not produce the same hash (collision resistance)."""
    assert hash_token("token_a") != hash_token("token_b")

def test_hash_token_output_is_64_chars():
    """SHA-256 hex digest is always exactly 64 characters — good to assert this explicitly."""
    result = hash_token("anything")
    assert len(result) == 64


def test_merge_cookie_config_returns_defaults_when_no_input():
    """
    When the user doesn't customize cookies, I should use secure defaults.
    These defaults are what every library user ships in production — they must be correct.
    """
    cookies = merge_cookie_config(user_config=None)

    assert cookies.session_token.options.http_only is True
    assert cookies.session_token.options.secure is True
    assert cookies.session_token.options.same_site == "lax"
    assert cookies.session_token.options.max_age == 30 * 24 * 60 * 60

def test_merge_cookie_config_csrf_is_not_http_only():
    """
    The CSRF token cookie must NOT be HttpOnly because my JS code needs to read it
    to include it in request headers for the double-submit CSRF pattern.
    """
    cookies = merge_cookie_config(user_config=None)
    assert cookies.csrf_token.options.http_only is False

def test_merge_cookie_config_state_and_pkce_are_short_lived():
    """
    The OAuth state, PKCE verifier, and nonce are only needed during the login redirect.
    They should expire quickly (15 minutes = 900 seconds) to minimize attack surface.
    """
    cookies = merge_cookie_config(user_config=None)
    assert cookies.state.options.max_age == 900
    assert cookies.pkce_code_verifier.options.max_age == 900
    assert cookies.nonce.options.max_age == 900

def test_merge_cookie_config_user_can_override_session_name():
    """
    A user should be able to rename the session cookie (e.g. to match their domain).
    I'm checking that user overrides actually take effect.
    """
    custom = PyAuthCookiesInput(
        session_token=CookieConfigInput(name="my_custom_session_cookie")
    )
    cookies = merge_cookie_config(user_config=custom)
    assert cookies.session_token.name == "my_custom_session_cookie"

def test_merge_cookie_config_user_override_preserves_other_defaults():
    """
    When a user overrides just the cookie name, the security options (HttpOnly, Secure, etc.)
    should remain at their defaults — I don't want the user accidentally disabling security.
    """
    custom = PyAuthCookiesInput(
        session_token=CookieConfigInput(name="my_custom_session_cookie")
    )
    cookies = merge_cookie_config(user_config=custom)
    assert cookies.session_token.options.http_only is True
    assert cookies.session_token.options.secure is True

def test_merge_cookie_config_user_can_override_same_site():
    """A user deploying across subdomains might need SameSite=None — that should work."""
    custom = PyAuthCookiesInput(
        session_token=CookieConfigInput(
            options=CookieOptionsInput(same_site="none")
        )
    )
    cookies = merge_cookie_config(user_config=custom)
    assert cookies.session_token.options.same_site == "none"

def test_merge_cookie_config_untouched_cookies_keep_defaults():
    """
    If I only override the session cookie, csrf_token, state, pkce, and nonce
    should all remain at their defaults unchanged.
    """
    custom = PyAuthCookiesInput(
        session_token=CookieConfigInput(name="overridden")
    )
    cookies = merge_cookie_config(user_config=custom)

    assert cookies.csrf_token.name == "py_auth_csrf"
    assert cookies.state.options.max_age == 900
