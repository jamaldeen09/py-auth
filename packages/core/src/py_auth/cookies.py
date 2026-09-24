

from .schemas import CookieConfig, CookieOptions, PyAuthCookies

COOKIES = PyAuthCookies(
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