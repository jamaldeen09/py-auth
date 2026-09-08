# py-auth-core

**Modular, framework-agnostic authentication primitives for Python backends.**

`py-auth-core` gives you secure session management, credential-based sign-in, CSRF protection, and a clean provider/adapter architecture — without forcing a specific ORM, web framework, or database on you.

[![PyPI version](https://img.shields.io/pypi/v/py-auth-core.svg)](https://pypi.org/project/py-auth-core/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-auth-core.svg)](https://pypi.org/project/py-auth-core/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [PyAuth](#pyauth-1)
  - [Providers](#providers)
  - [Adapters](#adapters)
  - [Cookies](#cookies)
- [API Reference](#api-reference)
  - [PyAuth class](#pyauth-class)
  - [CredentialsProvider](#credentialsprovider)
  - [BaseProvider](#baseprovider)
  - [Schemas & TypedDicts](#schemas--typeddicts)
  - [Exceptions](#exceptions)
- [Integrations](#integrations)
- [Available Adapters](#available-adapters)
- [Roadmap](#roadmap)
- [Security Notes](#security-notes)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- ✅ **Async-first** — every auth operation is a coroutine
- ✅ **Provider pattern** — plug in `CredentialsProvider` or use an upcoming provider
- ✅ **Adapter pattern** — swap the database layer without touching auth logic
- ✅ **Secure by default** — SHA-256 session-token hashing, `httpOnly` + `Secure` cookies, CSRF protection via `hmac.compare_digest`
- ✅ **Pydantic v2** request validation built-in
- ✅ **Framework-agnostic** — works with FastAPI, Starlette, Django, Flask, or any async Python backend
- ✅ **Typed throughout** — ships a `py.typed` marker; full TypedDict / Protocol coverage

---

## Installation

```bash
pip install py-auth-core
```

`py-auth-core` requires **Python ≥ 3.9** and **Pydantic ≥ 2.0**.

---

## Quick Start

Below is a minimal example using `py-auth-core` directly. If you're on **FastAPI**, see [Integrations](#integrations) — the official integration reduces this to a single line.

```python
from pydantic import BaseModel, EmailStr
from py_auth import PyAuth, CredentialsProvider


# 1. Define your credentials schema (Pydantic v2)
class LoginSchema(BaseModel):
    email: EmailStr
    password: str


# 2. Implement your authorization callback
async def authorize(credentials: dict) -> dict | None:
    """Check if the user exists — create them if not. Return None to reject."""
    user = await db.find_user_by_email(credentials["email"])

    if user:
        # Existing user — verify their password
        if not verify_password(credentials["password"], user.hashed_password):
            return None
        return {"id": str(user.id), "email": user.email, "name": user.name}

    # New user — create them and return their details
    new_user = await db.create_user(
        email=credentials["email"],
        hashed_password=hash_password(credentials["password"]),
    )
    return {"id": str(new_user.id), "email": new_user.email, "name": new_user.name}


# 3. Wire everything together
credentials_provider = CredentialsProvider(model=LoginSchema, authorize=authorize)

auth = PyAuth(
    adapter=my_adapter,  # any PyAuthAdapterProtocol-compliant adapter
    providers=[credentials_provider],
)
```

Once `auth` is set up, use it in your route handlers:

```python
# Sign in
result = await auth.signin_with_credentials(request_body)

# Verify an active session
result = await auth.verify_session(session_token, csrf_token)

# Sign out
result = await auth.signout(session_id)
```

Every method returns an `AuthResult` — a plain dict with `data` and `error` keys. Check `result["error"]` first; if it's `None` the operation succeeded.

---

## Core Concepts

### PyAuth

`PyAuth` is the central manager. It holds your adapter and providers and exposes async methods for every auth flow.

```
PyAuth
 ├── adapter          ← talks to your database
 ├── providers        ← one or more auth strategies
 └── cookies          ← merged cookie configuration
```

### Providers

A **provider** encapsulates a single authentication strategy. `py-auth-core` ships with one built-in provider today, with more on the way:

| Provider | Status | Description |
|---|---|---|
| `CredentialsProvider` | ✅ Available | Field-based sign-in (email/password, etc.) via a Pydantic model + async callback |
| `GoogleProvider` | 🔜 Coming soon | Google OAuth 2.0 |
| `GithubProvider` | 🔜 Coming soon | GitHub OAuth |
| `EmailProvider` | 🔜 Coming soon | Passwordless magic-link sign-in |

### Adapters

An **adapter** is any object that satisfies `PyAuthAdapterProtocol`. It handles all database I/O: creating sessions, updating sessions and looking up / deleting sessions.

`py-auth-core` validates your adapter at startup using a structural `Protocol` check — you'll get a clear `ConfigurationError` immediately if a required method is missing, rather than a cryptic failure later.

See [Available Adapters](#available-adapters) for ready-made options.

### Cookies

`py-auth-core` manages two cookies:

| Cookie | Default name | Purpose |
|---|---|---|
| Session token | `__Host-py_auth_session` | Authenticates the session — `httpOnly`, `Secure`, `SameSite=lax` |
| CSRF token | `py_auth_csrf` | Double-submit CSRF protection — JavaScript-readable (no `httpOnly`) |

Defaults are environment-aware: `secure=True` is always enforced when `ENVIRONMENT=production`. Override any value via `PyAuthCookiesInput`:

```python
from py_auth import PyAuth, PyAuthCookiesInput, CookieConfig, CookieOptions

auth = PyAuth(
    adapter=my_adapter,
    providers=[credentials_provider],
    cookies=PyAuthCookiesInput(
        session_token=CookieConfig(
            name="my_session",
            options=CookieOptions(max_age=7 * 24 * 60 * 60),  # 7 days
        )
    ),
)
```

---

## API Reference

### `PyAuth` class

```python
PyAuth(
    adapter: PyAuthAdapterProtocol,
    providers: list[BaseProvider] | None = None,
    cookies: PyAuthCookiesInput | None = None,
)
```

**Attributes**

| Attribute | Type | Description |
|---|---|---|
| `adapter` | `PyAuthAdapterProtocol` | The validated adapter instance |
| `cookies` | `dict[str, dict]` | Merged cookie config (name + options per token) |

---

#### `await auth.signin_with_credentials(request_body: dict) -> AuthResult`

Validates `request_body` with the `CredentialsProvider`'s Pydantic model, calls your `authorize` callback, creates a session, and returns tokens.

```python
result = await auth.signin_with_credentials({"email": "...", "password": "..."})
# Success:
# result["data"] = {"session_token": "...", "csrf_token": "...", "user": {...}}
# result["error"] = None
#
# Failure:
# result["data"] = None
# result["error"] = {"code": "CredentialsSignIn", "status_code": 401, "message": "..."}
```

---

#### `await auth.verify_session(session_token: str, csrf_token: str) -> AuthResult`

Hashes the session token, fetches the session from the adapter, checks expiry, and validates the CSRF token with `hmac.compare_digest`.

```python
result = await auth.verify_session(session_token, csrf_token)
# Success:  result["data"] = {"session": {...}}
# Failure:  result["error"] = {"code": "SessionExpired" | "InvalidCsrfToken" | ..., ...}
```

---

#### `await auth.signout(session_id: str) -> AuthResult`

Deletes the session identified by `session_id`.

```python
result = await auth.signout(session_id)
# result["data"] = {"signed_out": True}
```

---

#### `auth.get_auth_result(data=None, error=None) -> AuthResult`

Utility to build a standardised `AuthResult`. Useful in custom middleware or route guards.

---

### `CredentialsProvider`

```python
CredentialsProvider(
    model: Type[BaseModel],
    authorize: Callable[[dict], Any] | Callable[[dict], Awaitable[Any]],
)
```

| Parameter | Type | Description |
|---|---|---|
| `model` | `Type[BaseModel]` | Pydantic v2 model — the request body is validated against this before `authorize` is called |
| `authorize` | sync or async callable | Receives the validated payload as a plain `dict`. Return a truthy user dict on success, or `None` / falsy to trigger a `401` |

**Validation errors** are automatically serialised into a structured `422` response:

```json
{
  "error": {
    "code": "ValidationError",
    "status_code": 422,
    "message": "Validation failed.",
    "details": {
      "validation_errors": [
        {"field": "email", "errors": ["value is not a valid email address"]}
      ]
    }
  }
}
```

---

### `BaseProvider`

Abstract base class for all providers. Every provider that ships with `py-auth` extends this class. The `id` attribute is automatically derived from the class name (lowercased, with `"provider"` stripped) — e.g. `CredentialsProvider` → `"credentials"`.

```python
from py_auth import BaseProvider, AuthResult


class MyProvider(BaseProvider):
    async def handle_request(self, *args, **kwargs) -> AuthResult: ...
```

---

### Schemas & TypedDicts

#### `AuthResult`
```python
class AuthResult(TypedDict):
    data: Any | None
    error: AuthError | None
```

#### `AuthError`
```python
class AuthError(TypedDict, total=False):
    code: str  # machine-readable, e.g. "InvalidSessionToken"
    status_code: int  # HTTP status to send to the client
    message: str  # human-readable description
    details: dict  # optional structured detail (e.g. validation errors)
```

#### `PyAuthAdapterProtocol`
```python
class PyAuthAdapterProtocol(Protocol):
    async def create_session(self, session_data: dict) -> dict: ...
    async def get_session_by_session_token_hash(
        self, token_hash: str 
    ) -> dict | None: ...
    async def delete_session_by_session_token_hash(self, token_hash: str) -> None: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def update_session(
        self, session_id: str, updates: Dict
    ) -> dict | None: ...
```

> The adapter only manages sessions. User lookup and creation live entirely inside your
> `authorize()` callback — giving you full control over hashing, validation, and
> any other user-creation logic your app needs.

#### `CookieOptions`
```python
class CookieOptions(BaseModel):
    http_only: bool | None = None
    secure: bool | None = None
    same_site: Literal["lax", "strict", "none"] | None = None
    path: str | None = None
    domain: str | None = None
    max_age: int | None = None  # seconds
    expires: datetime | None = None
```

---

### Exceptions

All exceptions inherit from `PyAuthError` and carry a `status_code` attribute for easy HTTP mapping.

| Exception | Default `status_code` | When raised |
|---|---|---|
| `PyAuthError` | `500` | Base class; general catch-all |
| `ConfigurationError` | `500` | Adapter missing required methods, or provider not configured |
| `AdapterError` | `500` | Database engine setup failure |
| `DuplicateEntryError` | `409` | Unique constraint violation (e.g. duplicate session token) |
| `ForeignKeyViolationError` | `400` | Foreign key violation (e.g. referenced user no longer exists) |
| `RecordNotFoundError` | `404` | Requested record not found |

---

## Integrations

### FastAPI — `py-auth-fastapi`

The official FastAPI integration is a separate package that removes all the boilerplate of wiring `py-auth-core` into a FastAPI app. **It's a single line.**

You still configure the pieces you own — your providers and your `PyAuth` instance — and the integration handles everything else internally: mounting the auth routes, setting and reading cookies, and returning the right HTTP responses.

```python
# You set up your PyAuth instance as normal...
auth = PyAuth(adapter=my_adapter, providers=[credentials_provider])

# ...then hand it to the integration. That's it.
app.include_router(PyAuthFastAPI(auth))
```

The integration exposes ready-made routes for sign-in, session verification, and sign-out — no manual cookie handling, no manual response construction.

```bash
pip install py-auth-fastapi
```

---

## Available Adapters

| Package | Supported Databases | Install |
|---|---|---|
| [`py-auth-sqlalchemy`](https://pypi.org/project/py-auth-sqlalchemy/) | PostgreSQL (`asyncpg`), MySQL (`aiomysql`), SQLite (`aiosqlite`) | `pip install py-auth-sqlalchemy` |

> More adapters (Tortoise ORM, Motor/MongoDB, Beanie, etc.) are on the roadmap. Community contributions are welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Roadmap

`py-auth-core` is in early release (`0.0.1`). Here's what's planned:

**Providers**
- [ ] `GoogleProvider` — Google OAuth 2.0
- [ ] `GithubProvider` — GitHub OAuth
- [ ] `EmailProvider` — passwordless magic-link sign-in

**Integrations**
- [x] `py-auth-fastapi` — FastAPI integration
- [ ] `py-auth-django` — Django integration
- [ ] `py-auth-flask` — Flask / Quart integration
- [ ] `py-auth-litestar` — Litestar integration

**Adapters**
- [ ] Tortoise ORM adapter
- [ ] Motor (async MongoDB) adapter
- [ ] Beanie adapter

These will land as the project gains traction. If you'd like to see something added sooner, open an issue or a PR on [GitHub](https://github.com/jamaldeen09/py-auth).

---

## Security Notes

- **Session tokens are never stored in plain text.** Only a SHA-256 hex digest is persisted; the raw token lives only in the client cookie.
- **CSRF validation uses `hmac.compare_digest`** — immune to timing attacks.
- **Cookie defaults follow the `__Host-` prefix convention** for session cookies: `Secure`, `httpOnly`, `Path=/`, no explicit `Domain`. This provides the strongest possible same-origin binding.
- The **CSRF cookie intentionally omits `httpOnly`** so your frontend can read it and attach it as a request header for server-side comparison.
- In `ENVIRONMENT=production`, the `secure` flag is always forced to `True` on every cookie regardless of user configuration.

---

## Contributing

Want to build a new provider, adapter, or integration? See [CONTRIBUTING.md](./CONTRIBUTING.md) for architecture guidelines, how the adapter protocol works, and how to get started.

---

## License

MIT — see [LICENSE](./LICENSE) for details.
