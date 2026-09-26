# py-auth

Authentication for Python backends: **providers** for how people sign in, an **adapter** for how you store them, and optional **framework integrations** for HTTP.

Core does not know FastAPI. The SQLAlchemy adapter does not know your routes. The FastAPI package does not talk to the database. You compose the pieces you need.

Requires **Python 3.10+**.

[![py-auth-core](https://img.shields.io/pypi/v/py-auth-core.svg?label=py-auth-core)](https://pypi.org/project/py-auth-core/)
[![py-auth-sqlalchemy](https://img.shields.io/pypi/v/py-auth-sqlalchemy.svg?label=py-auth-sqlalchemy)](https://pypi.org/project/py-auth-sqlalchemy/)
[![py-auth-fastapi](https://img.shields.io/pypi/v/py-auth-fastapi.svg?label=py-auth-fastapi)](https://pypi.org/project/py-auth-fastapi/)
[![Python](https://img.shields.io/pypi/pyversions/py-auth-core.svg)](https://pypi.org/project/py-auth-core/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Packages

| Package | PyPI | Import | Role |
| --- | --- | --- | --- |
| [`py-auth-core`](packages/core) | [py-auth-core](https://pypi.org/project/py-auth-core/) | `py_auth` | Sign-in, sessions, CSRF, provider API. No HTTP, no SQL. |
| [`py-auth-sqlalchemy`](packages/adapters/sqlalchemy_adapter) | [py-auth-sqlalchemy](https://pypi.org/project/py-auth-sqlalchemy/) | `py_auth_sqlalchemy` | Async SQLAlchemy adapter. Your models, your engine. |
| [`py-auth-fastapi`](packages/integrations/fastapi_integration) | [py-auth-fastapi](https://pypi.org/project/py-auth-fastapi/) | `py_auth_fastapi` | `APIRouter`: routes, cookies, `HTTPException`s, session dependency. |

```mermaid
flowchart LR
  App[Your application]
  FastAPI[py-auth-fastapi]
  Core[py-auth-core]
  Adapter[Adapter protocol]
  SA[py-auth-sqlalchemy]
  Custom[Custom adapter]
  DB[(Database)]

  App --> FastAPI
  FastAPI --> Core
  App -.->|or call PyAuth directly| Core
  Core --> Adapter
  Adapter --> SA
  Adapter --> Custom
  SA --> DB
  Custom --> DB
```

Install only what you use. A CLI or a non-HTTP worker can take `py-auth-core` plus an adapter and never install FastAPI.

```bash
pip install py-auth-core py-auth-sqlalchemy py-auth-fastapi
pip install asyncpg   # or aiomysql, or aiosqlite
```

---

## How it fits together

1. **Adapter** — async methods that persist users, linked OAuth accounts, and sessions. `PyAuth` checks `PyAuthAdapterProtocol` at init and raises `ConfigurationError` if the object is incomplete.
2. **Providers** — how a sign-in attempt is proven. Built-ins: `CredentialsProvider` (your Pydantic body + `authorize` callback) and `GoogleProvider` (OIDC authorization code + PKCE). Looked up by id (`"credentials"`, `"google"`).
3. **`PyAuth`** — runs the provider, creates a session (raw token hashed with SHA-256, 30-day expiry), verifies sessions, signs out, and checks CSRF. Returns `{"data": ..., "error": ...}` and **does not set cookies**.
4. **Integration** (optional) — `PyAuthFastAPI` mounts routes, writes cookies from `auth.cookies`, and maps errors to FastAPI responses.

You can skip (4) and set cookies yourself. You can skip SQLAlchemy and implement the protocol against another store.

---

## Quick start (FastAPI + SQLAlchemy)

This is the usual stack. Full models (required **column names** vs your own constraints) live in the [SQLAlchemy README](packages/adapters/sqlalchemy_adapter/README.md). A runnable app is in [`examples/fastapi_app`](examples/fastapi_app).

```python
from uuid import uuid4
from datetime import datetime
from fastapi import FastAPI, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from py_auth import PyAuth, CredentialsProvider
from py_auth_sqlalchemy import SqlAlchemyAdapter, UTCDateTime
from py_auth_fastapi import PyAuthFastAPI

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image: Mapped[str | None] = mapped_column(nullable=True)
    password_hash: Mapped[str | None] = mapped_column(nullable=True)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid4()))
    session_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

# Account model omitted here; add it when you enable Google (see adapter README).

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
adapter = SqlAlchemyAdapter(engine, session_model=Session, user_model=User)

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
    providers=[CredentialsProvider(model=LoginSchema, authorize=authorize)],
)

app = FastAPI()
auth_router = PyAuthFastAPI(auth)
app.include_router(auth_router)

@app.get("/me")
async def me(session=Depends(auth_router.get_current_session())):
    return {"user_id": session["user_id"]}
```

Create tables yourself (`Base.metadata.create_all` or Alembic). The adapter does not migrate.

Typical client flow:

1. `GET /auth/csrf` — CSRF cookie + token in the JSON body.
2. `POST /auth/signin/credentials` with JSON credentials and header `x-csrf-token` matching the cookie.
3. Session cookie is set. `GET /auth/session` or `get_current_session()` on your routes.

---

## py-auth-core

Docs: [`packages/core/README.md`](packages/core/README.md) · PyPI: [py-auth-core](https://pypi.org/project/py-auth-core/)

```python
from py_auth import PyAuth, CredentialsProvider, GoogleProvider
```

### Results

Every `PyAuth` method returns the same shape. If `error` is set, the call failed; otherwise use `data`.

```python
result = await auth.signin_with_credentials({"email": email, "password": password})
if result["error"]:
    result["error"]["code"]          # e.g. "ValidationError", "CredentialsSignIn"
    result["error"]["status_code"]
    result["error"]["message"]
    result["error"].get("details")   # e.g. field errors on 422
else:
    result["data"]["session_token"]
    result["data"]["expires"]
```

Store `session_token` in a cookie (or let FastAPI do it). The database only ever sees `sha256(token)`.

### Credentials

`CredentialsProvider(model, authorize)`:

- Validates the body with your Pydantic model (sync `authorize` is fine).
- Success: return a **dict** with a string `id`.
- Wrong password / unknown user: return a falsy value → `401` / `CredentialsSignIn`.
- Invalid body: `422` / `ValidationError` with `details.validation_errors`.

`signin_with_credentials` authenticates, then creates a session.

### Google

`GoogleProvider(client_id, client_secret, redirect_uri, access_type="offline", prompt=None)` uses authorization code + PKCE, verifies the ID token against Google’s JWKS, then `get_or_create_user_and_link_account` on the adapter.

Without FastAPI:

1. `create_auth_url` → keep `state`, `code_verifier`, `nonce`.
2. Redirect the user.
3. `handle_google_callback(request_url, state, code_verifier, nonce)` → same session payload as credentials.

With FastAPI: `GET /auth/signin/google` and `GET /auth/google/callback` (see below). `redirect_uri` must match the callback URL you registered with Google (default integration path: `{origin}/auth/google/callback`).

### Sessions and CSRF

```python
await auth.verify_session(session_token)   # missing / invalid / expired → error; expired rows are deleted
await auth.signout(session_id)
auth.verify_csrf_double_submit(cookie_csrf, header_csrf)
```

Core **does not write cookies**. It holds names and flags on `auth.cookies`. Defaults:

| Cookie | Default name | Notes |
| --- | --- | --- |
| Session | `__Host-py_auth_session` | `HttpOnly`, `Secure`, `SameSite=Lax`, 30 days |
| CSRF | `py_auth_csrf` | **not** `HttpOnly` (the client must echo it), `Secure`, `SameSite=Lax`, 1 hour |
| OAuth `state` | `__Secure-py_auth.state` | `HttpOnly`, 15 minutes |
| PKCE verifier | `__Secure-py_auth.pkce.code_verifier` | `HttpOnly`, 15 minutes |
| OIDC `nonce` | `__Secure-py_auth.nonce` | `HttpOnly`, 15 minutes |

Override at construction:

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

### Custom providers

Subclass `BaseProvider` (`from py_auth._base import BaseProvider`), implement `authenticate(...) -> AuthResult`. The default `id` is the class name with `"provider"` stripped (`GoogleProvider` → `"google"`). Pass instances in `providers=[...]`.

### Exceptions adapters should raise

`py-auth-core` maps these into `AuthResult` errors (or FastAPI `HTTPException`s if you use the integration):

| Exception | Typical cause |
| --- | --- |
| `DuplicateEntryError` | Unique constraint (e.g. token hash collision) |
| `ForeignKeyViolationError` | Referenced row missing |
| `RecordNotFoundError` | Lookup missed |
| `AdapterError` | Engine / model setup |
| `ConfigurationError` | Adapter missing protocol methods |

---

## py-auth-sqlalchemy

Docs: [`packages/adapters/sqlalchemy_adapter/README.md`](packages/adapters/sqlalchemy_adapter/README.md) · PyPI: [py-auth-sqlalchemy](https://pypi.org/project/py-auth-sqlalchemy/)

Async only: `create_async_engine`, drivers `asyncpg` / `aiomysql` / `aiosqlite`. A sync engine is rejected.

You pass **your** declarative models. The adapter checks that **column names py-auth reads and writes exist**. That is not the same as `nullable`, `unique`, or foreign keys — those stay yours. Extra columns are allowed. A missing required name raises `AdapterError` at construction (`validate_sqlalchemy_model`).

| Model | On the adapter | Required *names* |
| --- | --- | --- |
| Session | Always | `id`, `session_token_hash`, `user_id`, `expires` |
| User | Optional; needed for user operations | `id`, `email`, `name`, `image`, `password_hash` |
| Account | Optional; needed for OAuth linking | `id`, `user_id`, `type`, `provider`, `provider_account_id`, `access_token`, `refresh_token`, `expires_at`, `token_type`, `scope`, `id_token`, `session_state` |

Use `UTCDateTime` for `expires` (timezone-aware UTC; naive values are rejected). Integrity errors become `DuplicateEntryError` / `ForeignKeyViolationError` / `PyAuthError`. Rows come back as dicts keyed by column name.

```python
adapter = SqlAlchemyAdapter(
    engine=engine,
    session_model=Session,
    user_model=User,
    account_model=Account,
)
```

Calling a user or account method when that model was not passed raises `AdapterError`.

### Custom adapters

Implement every method on `PyAuthAdapterProtocol` (users, accounts, sessions, `get_or_create_user_and_link_account`). Return dicts (or `None`). Raise the exceptions above so core can translate them. `PyAuth` will not start if a method is missing.

---

## py-auth-fastapi

Docs: [`packages/integrations/fastapi_integration/README.md`](packages/integrations/fastapi_integration/README.md) · PyPI: [py-auth-fastapi](https://pypi.org/project/py-auth-fastapi/)

`PyAuthFastAPI` subclasses `APIRouter`. Cookie names and flags come from `auth.cookies`, not from this package.

```python
auth_router = PyAuthFastAPI(auth)                    # prefix="/auth", tags=["Authentication"]
auth_router = PyAuthFastAPI(auth, prefix="/api/auth")
app.include_router(auth_router)
```

Extra keyword arguments go to `APIRouter`.

| Method | Path | CSRF | Behavior |
| --- | --- | --- | --- |
| `GET` | `/auth/csrf` | No | Return CSRF token; set cookie if missing |
| `POST` | `/auth/signin/credentials` | Yes | JSON → `signin_with_credentials`; set session cookie |
| `POST` | `/auth/signout` | Yes | Delete session; clear session + CSRF cookies |
| `GET` | `/auth/session` | No | `id`, `user_id`, `expires` |
| `GET` | `/auth/signin/google` | No | Redirect to Google; store state / PKCE / nonce cookies. Requires `GoogleProvider`. |
| `GET` | `/auth/google/callback` | No | Finish Google sign-in; set session cookie; clear OAuth cookies |

CSRF is double-submit: CSRF **cookie** vs `x-csrf-token` **header**.

Errors:

```json
{
  "detail": {
    "success": false,
    "message": "...",
    "error": { "status_code": 401, "code": "InvalidSession", "details": {} }
  }
}
```

Protect your own routes:

```python
@app.get("/protected")
async def protected(session=Depends(auth_router.get_current_session())):
    ...

@app.post("/profile")
async def update_profile(
    session=Depends(auth_router.get_current_session(add_csrf_verification=True)),
):
    ...
```

`get_current_session()` reads the session cookie and calls `verify_session`. `verify_csrf()` is also available on its own.

---

## Repository

```
packages/
  core/                          # py-auth-core
  adapters/sqlalchemy_adapter/   # py-auth-sqlalchemy
  integrations/fastapi_integration/  # py-auth-fastapi
examples/fastapi_app/            # sample app (credentials + Google)
tests/
compose.yml                      # demo Postgres + test Postgres/MySQL
```

Each package is published separately (`src/` layout, its own `pyproject.toml` and README). The root `pyproject.toml` is for the workspace (pytest), not a combined installable.

Example app: [`examples/fastapi_app`](examples/fastapi_app). With Docker: `compose.yml` (`fastapi-app` + `app-postgres`). Tests use `test-postgres` / `test-mysql` (and SQLite in-process where configured).

---

## Contributing

Issues and pull requests are welcome. Development setup, tests, and conventions: [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT. See [LICENSE](LICENSE).
