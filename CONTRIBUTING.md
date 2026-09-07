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
 └── adapters/
     └── sqlalchemy-adapter/      # py-auth-sqlalchemy
         └── src/py_auth_sqlalchemy/
             ├── core.py          # SqlAlchemyAdapter
             └── utils.py         # DB error translation, validation helpers
```

---

## Building an Adapter

An adapter is any Python class that satisfies `PyAuthAdapterProtocol`. It abstracts all database I/O so the core library stays database-agnostic.

### The `PyAuthAdapterProtocol`

```python
from py_auth import PyAuthAdapterProtocol

class PyAuthAdapterProtocol(Protocol):
    async def create_session(self, session_data: dict) -> dict: ...
    async def get_session_by_session_token_hash(self, session_token_hash: str) -> dict | None: ...
    async def delete_session_by_session_token_hash(self, session_token_hash: str) -> None: ...
    async def delete_session_by_id(self, session_id: str) -> None: ...
```

Every method must be `async`.

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

- [ ] All five protocol methods implemented and `async`
- [ ] `create_session` returns the persisted record as a `dict`
- [ ] Database errors translated into the correct `py-auth` exceptions
- [ ] Validated with `AdapterContainer(adapter=MyAdapter(...))` — this runs the protocol check
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

A framework integration mounts `py-auth` into a specific web framework so end users get a one-liner setup. The integration should:

1. Accept a configured `PyAuth` instance
2. Mount sign-in, verify, and sign-out routes automatically
3. Handle cookie reading/writing internally
4. Not require the user to write route handlers

See `py-auth-fastapi` as the reference implementation.

Naming convention: `py-auth-<framework>` (e.g. `py-auth-django`, `py-auth-litestar`).

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
