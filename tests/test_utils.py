"""Tests for py_auth.utils — token helpers, auth results, cookie merging."""

from __future__ import annotations


from py_auth.schemas import CookieConfigInput, CookieOptionsInput, PyAuthCookiesInput
from py_auth.utils import (
    generate_token,
    get_auth_result,
    hash_token,
    merge_cookie_config,
)


def test_generate_token_default_length() -> None:
    token = generate_token()
    # token_urlsafe(32) -> 43 base64 chars (no padding)
    assert len(token) == 43
    assert isinstance(token, str)


def test_generate_token_custom_length() -> None:
    assert len(generate_token(num_bytes=48)) == 64


def test_generate_token_is_unique() -> None:
    tokens = {generate_token() for _ in range(200)}
    assert len(tokens) == 200


def test_hash_token_deterministic_sha256() -> None:
    digest = hash_token("abc")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert hash_token("abc") == digest


def test_hash_token_differs_per_input() -> None:
    assert hash_token("abc") != hash_token("abd")


def test_get_auth_result_data_only() -> None:
    assert get_auth_result(data={"ok": True}) == {"data": {"ok": True}, "error": None}


def test_get_auth_result_error_only() -> None:
    error = {"code": "Nope", "status_code": 401, "message": "no"}
    result = get_auth_result(error=error)
    assert result["data"] is None
    assert result["error"] == error


def test_get_auth_result_empty() -> None:
    assert get_auth_result() == {"data": None, "error": None}


def test_merge_cookie_config_defaults() -> None:
    merged = merge_cookie_config()
    assert merged.session_token.name == "__Host-py_auth_session"
    assert merged.session_token.options.http_only is True
    assert merged.session_token.options.secure is True
    assert merged.session_token.options.same_site == "lax"
    assert merged.session_token.options.max_age == 30 * 24 * 60 * 60
    assert merged.csrf_token.name == "py_auth_csrf"
    assert merged.csrf_token.options.http_only is False
    assert merged.csrf_token.options.max_age == 60 * 60


def test_merge_cookie_config_renames() -> None:
    merged = merge_cookie_config(
        PyAuthCookiesInput(
            session_token=CookieConfigInput(name="sid"),
            csrf_token=CookieConfigInput(name="xsrf"),
        )
    )
    assert merged.session_token.name == "sid"
    assert merged.csrf_token.name == "xsrf"
    # Unspecified options still inherit defaults.
    assert merged.session_token.options.secure is True
    assert merged.csrf_token.options.same_site == "lax"


def test_merge_cookie_config_partial_options_merge() -> None:
    merged = merge_cookie_config(
        PyAuthCookiesInput(
            session_token=CookieConfigInput(
                options=CookieOptionsInput(http_only=False, max_age=3600)
            )
        )
    )
    opts = merged.session_token.options
    assert opts.http_only is False
    assert opts.max_age == 3600
    # Other options retain defaults.
    assert opts.secure is True
    assert opts.path == "/"


def test_get_logger_namespace() -> None:
    from py_auth.utils import get_logger

    assert get_logger().name == "py_auth"