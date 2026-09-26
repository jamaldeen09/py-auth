# py-auth-core

Authentication logic for Python backends, independent of any web framework or database.

You give it a **storage adapter** (how users and sessions are saved) and one or more **providers** (how people sign in). `PyAuth` then handles sign-in, session tokens, and CSRF checks. It does not serve HTTP routes or set cookies — your app, or a package like [`py-auth-fastapi`](https://pypi.org/project/py-auth-fastapi/), does that.

Requires Python 3.10+.

## Install

```bash
pip install py-auth-core
```

You still need an adapter that talks to your database. [`py-auth-sqlalchemy`](https://pypi.org/project/py-auth-sqlalchemy/) is the ready-made option.

## Quick start

```python
from pydantic import BaseModel, EmailStr
from py_auth import PyAuth, CredentialsProvider, GoogleProvider

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

async def authorize(credentials: dict):
    user = await adapter.get_user_by_email(credentials["email"])
    if not user or not verify_password(credentials["password"], user["password_hash"]):
        return None
    return user  # must include a string "id"

auth = PyAuth(
    adapter=adapter,
    providers=[
        CredentialsProvider(model=LoginSchema, authorize=authorize),
        GoogleProvider(
            client_id="...",
            client_secret="...",
            redirect_uri="https://example.com/auth/callback/google",
        ),
    ],
)
```

Every auth method returns the same shape: `{"data": ..., "error": ...}`. If `error` is set, the call failed — read `code`, `status_code`, and `message`. If it is not set, use `data`.

```python
result = await auth.signin_with_credentials({"email": email, "password": password})
if result["error"]:
    code = result["error"]["code"]          # e.g. "ValidationError", "CredentialsSignIn"
    status = result["error"]["status_code"]
    message = result["error"]["message"]
else:
    session_token = result["data"]["session_token"]
    expires = result["data"]["expires"]
```

On success, store `session_token` in a cookie (or let your framework integration do it). That token is what `verify_session` uses later.

## Credentials

`CredentialsProvider` is email/password (or any fields you define). It first validates the request body with your Pydantic model, then calls your `authorize` function (sync or async). You decide how to look up the user and check the password.

- Success: return a user **dict** that includes a string `id`.
- Wrong credentials: return a falsy value. The result is `401` with code `CredentialsSignIn`.
- Invalid body: `422` with per-field messages under `error["details"]`.

`signin_with_credentials` runs the provider, then creates a session if `authorize` succeeded.

## Google OIDC

`GoogleProvider` signs people in with Google. It uses the authorization-code flow with PKCE, checks the ID token against Google’s public keys, then creates or links the user through your adapter.

Typical flow:

1. Call `create_auth_url` to get the Google URL. Keep the returned `state`, `code_verifier`, and `nonce` (usually in short-lived cookies).
2. Send the user to Google.
3. When they come back, pass the callback URL and those three values in:

```python
result = await auth.handle_google_callback(
    request_url=str(request.url),
    state=state,
    code_verifier=code_verifier,
    nonce=nonce,
)
```

A successful result is a new session, same as credentials: `data` has `session_token` and `expires`.

## Sessions and CSRF

```python
await auth.verify_session(session_token)   # looks up the hashed token; rejects missing/expired
await auth.signout(session_id)             # deletes the session row
auth.verify_csrf_double_submit(cookie_csrf_token, submitted_csrf_token)
```

The raw session token is never stored. Only a hash is saved, and sessions expire after 30 days. If `verify_session` finds an expired session, it deletes it.

CSRF: the browser holds a CSRF cookie; the client also sends the same value in the header. `verify_csrf_double_submit` checks if they match.

This package does **not** write cookies. It only keeps names and flags on `auth.cookies` (session, CSRF, OAuth state, PKCE verifier, nonce). Defaults: `__Host-` / `__Secure-` prefixes, `HttpOnly`, `Secure`, `SameSite=Lax`. You can override when you construct `PyAuth`:

```python
from py_auth import PyAuthCookiesInput, CookieConfigInput, CookieOptionsInput

auth = PyAuth(
    adapter=adapter,
    cookies=PyAuthCookiesInput(
        session_token=CookieConfigInput(
            name="my_session",
            options=CookieOptionsInput(same_site="strict"),
        )
    ),
)
```

## Adapter

`adapter` is how py-auth reads and writes users, linked accounts, and sessions. It must implement `PyAuthAdapterProtocol` (async methods). If it does not, `PyAuth` raises a `ConfigurationError` on initialization.

Your adapter should raise these when the database says so — py-auth maps them into `AuthResult` errors:

| Exception | When |
| --- | --- |
| `DuplicateEntryError` | Unique constraint (e.g. session token collision) |
| `ForeignKeyViolationError` | Referenced row missing (e.g. user deleted) |
| `RecordNotFoundError` | Lookup missed (e.g. sign-out of a gone session) |
| `AdapterError` | Adapter/engine setup failed |

## Custom providers

Subclass `BaseProvider`, give it an `id`, implement `authenticate(...) -> AuthResult`, and pass it in `providers=[...]`. Built-in providers are looked up by id (`"credentials"`, `"google"`).

## License

MIT
