# Contributing to py-auth

Thank you for your interest in contributing! `py-auth` is designed to be modular and extensible — new providers, adapters, and integrations can be added without touching the core library.

This guide explains the architecture, the contracts you need to implement, and the conventions to follow.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Building an Adapter](#building-an-adapter)
  - [The PyAuthAdapterProtocol](#the-pyauthadapterprotocol)
  - [Required session_data fields](#required-session_data-fields)
  - [Error conventions](#error-conventions)
  - [Adapter checklist](#adapter-checklist)
- [Building a Provider](#building-a-provider)
  - [BaseProvider](#baseprovider)
  - [Provider checklist](#provider-checklist)
- [Building a Framework Integration](#building-a-framework-integration)
  - [Integration Responsibilities](#integration-responsibilities)
  - [Example Integration Architecture](#example-integration-architecture-py-auth-fastapi)
  - [Integration checklist](#integration-checklist)
- [Package layout & naming](#package-layout--naming)
- [Development setup](#development-setup)
- [Pull Request guidelines](#pull-request-guidelines)

---

## Project Structure

```
packages/
 ├── core/                        # py-auth (core library)
 │   └── src/py_auth/
 │       ├── core.py              # PyAuth manager
 │       ├── base.py              # BaseProvider ABC
 │       ├── schemas.py           # TypedDicts, Pydantic models, Protocol
 │       ├── exceptions.py        # All py-auth exception classes
 │       ├── utils.py             # Token generation, hashing, cookie merging
 │       └── providers/
 │           └── credentials.py   # CredentialsProvider
 ├── adapters/
 │   └── sqlalchemy-adapter/      # py-auth-sqlalchemy
 │       └── src/py_auth_sqlalchemy/
 │           ├── core.py          # SqlAlchemyAdapter
 │           └── utils.py         # DB error translation, validation helpers
 └── integrations/
     └── fastapi-integration/     # py-auth-fastapi
         └── src/py_auth_fastapi/
             ├── core.py          # PyAuthFastAPI APIRouter
             └── utils.py         # Exception handling helpers
```

---

## Building an Adapter

An adapter is any Python class that satisfies `PyAuthAdapterProtocol`. It abstracts all database I/O so the core library stays database-agnostic.

### The `PyAuthAdapterProtocol`

```python
from typing import Protocol, Any, Dict, Optional
from py_auth import PyAuthAdapterProtocol

class PyAuthAdapterProtocol(Protocol):
    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]: ...
    async def get_session_by_session_token_hash(
        self, session_token_hash: str
    ) -> Optional[Dict[str, Any]]: ...
    async def delete_session_by_session_token_hash(
        self, session_token_hash: str
    ) -> None: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def update_session(
        self, session_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]: ...
```

Every method must be `async`.

#### Protocol Methods Explained

| Method | Signature | Description |
|---|---|---|
| `create_session` | `(session_data: dict) -> dict` | Inserts and persists a new session record, returning it as a dictionary. |
| `get_session_by_session_token_hash` | `(session_token_hash: str) -> dict \| None` | Looks up an active session by the SHA-256 hash of its session token, or returns `None` if not found. |
| `delete_session_by_session_token_hash` | `(session_token_hash: str) -> None` | Deletes a session by its token hash (called during expired session cleanup). |
| `delete_session` | `(session_id: str) -> None` | Deletes a session by its primary key ID (called during user signout). |
| `update_session` | `(session_id: str, updates: dict) -> dict \| None` | Updates fields on a session record (e.g. rotating `csrf_token`), returning the updated session dict or `None` if not found. |

### Required `session_data` fields

When `PyAuth` calls `create_session`, it always passes a dict with these exact keys:

| Key | Type | Description |
|---|---|---|
| `session_token_hash` | `str` | SHA-256 hex digest of the raw session token |
| `user_id` | `Any` | The `id` field from the `authorize` callback's return value |
| `csrf_token` | `str` | Raw CSRF token to be stored for later comparison |
| `expires` | `datetime` | Naive UTC datetime 30 days from now |

Your `create_session` must persist these and return the created record as a plain `dict`.

### Error conventions

Translate database-specific errors into the appropriate `py-auth` exceptions so the core retry and error-handling logic works correctly:

| Situation | Raise |
|---|---|
| Unique / duplicate key on `session_token_hash` | `DuplicateEntryError` — triggers the built-in 3-retry token regeneration |
| Foreign key violation (e.g. user doesn't exist) | `ForeignKeyViolationError` |
| Record not found | `RecordNotFoundError` |
| Any other DB error | `AdapterError` or `PyAuthError` |

```python
from py_auth.exceptions import DuplicateEntryError, ForeignKeyViolationError, AdapterError
```

### Adapter checklist

- [ ] All five protocol methods implemented and `async` (`create_session`, `get_session_by_session_token_hash`, `delete_session_by_session_token_hash`, `delete_session`, `update_session`)
- [ ] `create_session` returns the persisted record as a `dict`
- [ ] `update_session` applies updates and returns the updated record as a `dict` (or `None` if not found)
- [ ] Database errors translated into the correct `py-auth` exceptions
- [ ] Validated with `AdapterContainer(adapter=MyAdapter(...))` — this runs the runtime `PyAuthAdapterProtocol` check
- [ ] Package named `py-auth-<name>` (e.g. `py-auth-motor`, `py-auth-tortoise`)

---

## Building a Provider

A provider encapsulates a single authentication strategy (OAuth, magic link, passkey, etc.).

### `BaseProvider`

```python
from py_auth import BaseProvider, AuthResult

class MyProvider(BaseProvider):
    """One-line description of what this provider does."""

    def __init__(self, ...):
        super().__init__()   # sets self.id automatically
        ...

    async def handle_request(self, *args, **kwargs) -> AuthResult:
        # On success:
        return {"data": user_dict, "error": None}

        # On failure:
        return {
            "data": None,
            "error": {
                "code": "SomeErrorCode",
                "status_code": 401,
                "message": "Human-readable message.",
            },
        }
```

`self.id` is automatically set from the class name — `MyProvider` → `"my"`. Make sure it's unique if you're registering multiple providers with the same `PyAuth` instance.

### Provider checklist

- [ ] Subclasses `BaseProvider` and calls `super().__init__()`
- [ ] `handle_request` is `async` and always returns a valid `AuthResult`
- [ ] Never raises an uncaught exception — wrap with try/except and return an `error` dict
- [ ] Uses `get_logger()` for internal logging (`from py_auth.utils import get_logger`)
- [ ] No hard dependency on a specific web framework

---

## Building a Framework Integration

A framework integration mounts `py-auth` into a specific web framework (e.g. FastAPI, Starlette, Flask, Django, Litestar) so end users get a one-liner setup.

See `py-auth-fastapi` as the reference implementation.

Naming convention: `py-auth-<framework>` (e.g. `py-auth-fastapi`, `py-auth-django`, `py-auth-litestar`).

### Integration Responsibilities

A complete framework integration should:

1. **Accept a configured `PyAuth` instance** — typically via a router or extension class (e.g. `PyAuthFastAPI(APIRouter)`).
2. **Mount the standard auth routes automatically**:
   - `POST /signin` — parses credentials from the request body, calls `await auth.signin_with_credentials(request_body)`, and sets session and CSRF cookies on the response.
   - `POST /signout` — a protected route that calls `await auth.signout(session["id"])` and clears auth cookies with matching attributes.
   - `GET /session` (`get_session`) — a protected route that fetches the active session, rotates the CSRF token via `await auth.update_session_csrf_token(session["id"])`, sets the new CSRF cookie on the response, and returns the active session payload.
3. **Provide route protection**:
   - Expose a dependency or middleware (e.g. `get_current_session()`) that extracts the session and CSRF tokens from request cookies, validates them with `await auth.verify_session(session_token, csrf_token)`, and returns the verified session dict.
4. **Manage cookies dynamically**:
   - Respect configured `CookieConfig` and `CookieOptions` (`path`, `domain`, `secure`, `httponly`, `samesite`, `max_age`, `expires`) from `auth.cookies["session_token"]` and `auth.cookies["csrf_token"]`.
   - Provide helper methods (e.g. `_set_auth_cookie` and `_clear_auth_cookie`) to maintain consistent cookie headers.
5. **Translate error responses**:
   - Provide a helper (e.g. `raise_auth_exception`) that translates `py-auth` `AuthError` dicts (`code`, `status_code`, `message`, `details`) into framework-native HTTP exceptions (such as `fastapi.HTTPException`).

### Example Integration Architecture (`py-auth-fastapi`)

```python
from fastapi import APIRouter, Request, Response, Depends
from py_auth import PyAuth
from py_auth.schemas import CookieConfig
from .utils import raise_auth_exception

class PyAuthFastAPI(APIRouter):
    def __init__(self, auth: PyAuth, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth = auth
        self._register_routes()

    def get_current_session(self):
        """Dependency factory for protecting routes."""
        async def dependency(request: Request):
            session_token = request.cookies.get(self.auth.cookies["session_token"]["name"])
            csrf_token = request.cookies.get(self.auth.cookies["csrf_token"]["name"])
            result = await self.auth.verify_session(session_token, csrf_token)

            if result.get("error"):
                raise_auth_exception(result["error"])

            return result["data"]["session"]
        return dependency

    def _register_routes(self):
        @self.post("/signin")
        async def signin(request: Request, response: Response):
            request_body = await request.json()
            result = await self.auth.signin_with_credentials(request_body)
            if result.get("error"):
                raise_auth_exception(result["error"])

            data = result["data"]
            self._set_auth_cookie(response, self.auth.cookies["session_token"], data["session_token"])
            self._set_auth_cookie(response, self.auth.cookies["csrf_token"], data["csrf_token"])
            return {"success": True, "message": "You have successfully signed in."}

        @self.post("/signout")
        async def signout(response: Response, session=Depends(self.get_current_session())):
            await self.auth.signout(session["id"])
            self._clear_auth_cookie(response, self.auth.cookies["session_token"])
            self._clear_auth_cookie(response, self.auth.cookies["csrf_token"])
            return {"success": True, "message": "You have successfully signed out."}

        @self.get("/session")
        async def get_session(response: Response, session=Depends(self.get_current_session())):
            result = await self.auth.update_session_csrf_token(session["id"])
            if result.get("error"):
                raise_auth_exception(result["error"])

            self._set_auth_cookie(response, self.auth.cookies["csrf_token"], result["data"]["csrf_token"])
            return {
                "success": True,
                "message": "Session is active.",
                "session": {
                    "id": session.get("id"),
                    "user_id": session.get("user_id"),
                    "expires": session.get("expires"),
                },
            }
```

### Integration checklist

- [ ] Accepts a configured `PyAuth` instance
- [ ] Mounts `POST /signin`, `POST /signout`, and `GET /session` (`get_session`) routes
- [ ] Provides a dependency or middleware (`get_current_session`) for route protection
- [ ] Rotates CSRF token on `GET /session` via `auth.update_session_csrf_token(session["id"])`
- [ ] Handles setting and clearing cookies according to `auth.cookies` configuration
- [ ] Translates `AuthError` responses into native framework HTTP exceptions
- [ ] Package named `py-auth-<framework>` and placed under `packages/integrations/<framework>-integration/`

---

## Package layout & naming

New packages should live under `packages/adapters/<name>/` or `packages/integrations/<name>/` and follow the same `src/` layout as the existing packages:

```
packages/adapters/my-adapter/
 ├── pyproject.toml
 ├── README.md
 ├── LICENSE
 └── src/
     └── py_auth_myadapter/
         ├── __init__.py
         ├── py.typed
         └── core.py
```

Minimum `pyproject.toml` dependencies:
```toml
dependencies = [
    "py-auth>=0.0.1",
]
```

---

## Development setup

```bash
# Clone the repo
git clone https://github.com/jamaldeen09/py-auth.git
cd py-auth

# Set up the core package in editable mode
cd packages/core
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Or for the sqlalchemy adapter
cd packages/adapters/sqlalchemy-adapter
pip install -e .
```

---

## Pull Request guidelines

- Keep PRs focused — one adapter, provider, or integration per PR
- Include a `README.md` for new packages
- Ensure your adapter passes `AdapterContainer(adapter=YourAdapter(...))` without raising
- Open an issue first for large changes so we can discuss design before you build

---

Thanks for contributing! 🎉
