# py-auth-sqlalchemy

**High-performance, async SQLAlchemy 2.0 adapter for [py-auth-core](https://pypi.org/project/py-auth-core/).**

Plug this adapter into `PyAuth` to get automatic, async session persistence across PostgreSQL, MySQL, and SQLite — with built-in error translation from SQLAlchemy exceptions into `py-auth-core` exceptions.

[![PyPI version](https://img.shields.io/pypi/v/py-auth-sqlalchemy.svg)](https://pypi.org/project/py-auth-sqlalchemy/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-auth-sqlalchemy.svg)](https://pypi.org/project/py-auth-sqlalchemy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Supported Databases](#supported-databases)
- [Quick Start](#quick-start)
- [Session Model Requirements](#session-model-requirements)
- [API Reference](#api-reference)
  - [SqlAlchemyAdapter](#sqlalchemyadapter)
  - [Error Translation](#error-translation)
- [Full FastAPI Example](#full-fastapi-example)
- [Security Notes](#security-notes)
- [License](#license)

---

## Features

- ✅ **Async-native** — built entirely on SQLAlchemy `AsyncEngine` + `AsyncSession`
- ✅ **BYO model** — bring your own declarative SQLAlchemy model; extra columns are fine
- ✅ **Strict validation at startup** — engine type and required model columns are checked immediately, before any request is served
- ✅ **Automatic error translation** — `IntegrityError` → `DuplicateEntryError` / `ForeignKeyViolationError`, `NoResultFound` → `RecordNotFoundError`
- ✅ **Session-only** — user lookup and creation live in your `authorize()` callback, giving you full control

---

## Installation

```bash
pip install py-auth-sqlalchemy
```

Then install the async driver for your database:

```bash
# PostgreSQL
pip install asyncpg

# MySQL / MariaDB
pip install aiomysql

# SQLite
pip install aiosqlite
```

**Requirements:** Python ≥ 3.9, SQLAlchemy ≥ 2.0, py-auth-core ≥ 0.0.1.

---

## Supported Databases

| Database | Async driver | Connection URL prefix |
|---|---|---|
| PostgreSQL | `asyncpg` | `postgresql+asyncpg://` |
| MySQL / MariaDB | `aiomysql` | `mysql+aiomysql://` |
| SQLite | `aiosqlite` | `sqlite+aiosqlite:///` |

The adapter validates the driver at startup and raises `AdapterError` for unsupported drivers.

---

## Quick Start

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String
import uuid, datetime

from py_auth_sqlalchemy import SqlAlchemyAdapter
from py_auth import PyAuth, CredentialsProvider

# 1. Define your SQLAlchemy session model
class Base(DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = "sessions"

    # Required columns — do NOT rename these
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    expires: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    # Any extra columns you want are fine
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

# 2. Create the async engine
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")

# 3. Create the adapter
adapter = SqlAlchemyAdapter(engine=engine, session_model=Session)

# 4. Wire up PyAuth
auth = PyAuth(adapter=adapter, providers=[credentials_provider])
```

---

## Session Model Requirements

Your SQLAlchemy session model **must** define the following columns with exactly these names:

| Column | Recommended type | Description |
|---|---|---|
| `id` | `String` / `UUID` (primary key) | Unique session identifier |
| `session_token_hash` | `String` (unique, non-null) | SHA-256 hash of the raw session token |
| `user_id` | `String` / `UUID` (non-null) | Reference to the owning user |
| `csrf_token` | `String` (non-null) | Raw CSRF token for double-submit validation |
| `expires` | `DateTime` (non-null) | Naive UTC datetime when the session expires |

> **Extra columns are allowed.** You can freely add `created_at`, `ip_address`, `user_agent`, or any other columns your application needs.

If any required column is missing, `SqlAlchemyAdapter.__init__` raises `AdapterError` with a descriptive message listing the missing columns.

---

## API Reference

### `SqlAlchemyAdapter`

```python
SqlAlchemyAdapter(
    engine: AsyncEngine,
    session_model: Type[Any],
)
```

| Parameter | Type | Description |
|---|---|---|
| `engine` | `AsyncEngine` | An async SQLAlchemy engine created via `create_async_engine` |
| `session_model` | `Type[DeclarativeBase]` | Your SQLAlchemy declarative model class for sessions |

Both parameters are validated immediately in `__init__`:
- `engine` must be an `AsyncEngine` using a supported async driver (`asyncpg`, `aiomysql`, `aiosqlite`)
- `session_model` must be a valid SQLAlchemy declarative class with all required columns present

**Methods** (all async)

| Method | Signature | Description |
|---|---|---|
| `create_session` | `(session_data: dict) -> dict` | Inserts a new session row and returns it as a dict |
| `get_session_by_session_token_hash` | `(token_hash: str) -> dict \| None` | Fetches a session by hashed token, or `None` if not found |
| `update_session` | `(session_id: str, updates: dict) -> dict \| None` | Updates fields on an existing session row and returns the updated record as a dict, or `None` if not found |
| `delete_session_by_session_token_hash` | `(token_hash: str) -> None` | Deletes a session by hashed token |
| `delete_session` | `(session_id: Any) -> None` | Deletes a session by its primary key / ID |

---

### Error Translation

The adapter automatically maps SQLAlchemy exceptions to `py-auth-core` exceptions so `PyAuth` can handle them uniformly:

| SQLAlchemy exception | py-auth-core exception | Trigger |
|---|---|---|
| `IntegrityError` (unique / duplicate) | `DuplicateEntryError` (409) | Duplicate `session_token_hash` |
| `IntegrityError` (foreign key) | `ForeignKeyViolationError` (400) | `user_id` references a non-existent user |
| `NoResultFound` | `RecordNotFoundError` (404) | Query returned no rows |
| Any other `Exception` | `PyAuthError` (500) | Unexpected database error |

`PyAuth.signin_with_credentials` automatically retries on `DuplicateEntryError` (up to 3 times with a fresh token) without any extra code on your part.

---

## Full FastAPI Example

This example shows the full flow: user lookup, sign-in, and sign-up all handled inside a single `authorize()` callback — no separate signup endpoint needed.

```python
import datetime, uuid
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, select

from py_auth import PyAuth, CredentialsProvider
from py_auth_sqlalchemy import SqlAlchemyAdapter

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- SQLAlchemy models ---
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    expires: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

# --- Engine and adapter ---
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
adapter = SqlAlchemyAdapter(engine=engine, session_model=Session)

# --- Credentials schema ---
class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# --- authorize() handles both sign-in and sign-up ---
async def authorize(credentials: dict) -> dict | None:
    """
    Check if the user exists:
      - If yes, verify their password and return their details.
      - If no, create them and return the new user's details.
      - Return None to reject (wrong password).
    """
    async with AsyncSession(engine) as db:
        result = await db.execute(select(User).where(User.email == credentials["email"]))
        user = result.scalar_one_or_none()

        if user:
            # Existing user — verify credentials
            if not pwd_ctx.verify(credentials["password"], user.hashed_password):
                return None
            return {"id": user.id, "email": user.email}

        # New user — create and return
        async with db.begin():
            new_user = User(
                email=credentials["email"],
                hashed_password=pwd_ctx.hash(credentials["password"]),
            )
            db.add(new_user)
            await db.flush()
            await db.refresh(new_user)
        return {"id": new_user.id, "email": new_user.email}

# --- Wire up PyAuth ---
auth = PyAuth(
    adapter=adapter,
    providers=[CredentialsProvider(model=LoginSchema, authorize=authorize)],
)

# --- FastAPI routes ---
app = FastAPI()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post("/auth/signin")
async def signin(request: Request, response: Response):
    body = await request.json()
    result = await auth.signin_with_credentials(body)
    if result["error"]:
        return result
    data = result["data"]
    response.set_cookie(auth.cookies["session_token"]["name"], data["session_token"],
                        **auth.cookies["session_token"]["options"])
    response.set_cookie(auth.cookies["csrf_token"]["name"], data["csrf_token"],
                        **auth.cookies["csrf_token"]["options"])
    return {"user": data["user"]}

@app.get("/auth/verify")
async def verify(request: Request):
    session_token = request.cookies.get(auth.cookies["session_token"]["name"])
    csrf_token = request.cookies.get(auth.cookies["csrf_token"]["name"])
    return await auth.verify_session(session_token, csrf_token)

@app.post("/auth/signout")
async def signout(session_id: str):
    return await auth.signout(session_id)
```

---

## Security Notes

- **Only hashed session tokens are stored in the database.** The raw token is set in a `httpOnly` cookie and never persisted.
- **Always hash passwords** before persisting — use bcrypt, argon2, or scrypt. Never store plain text.
- Use `expire_on_commit=False` (set by the adapter automatically) so ORM instances remain accessible after `session.commit()`.
- For PostgreSQL, ensure your `Session` table has a **unique index** on `session_token_hash` at the database level to guarantee the uniqueness constraint that `DuplicateEntryError` depends on.

---

## License

MIT — see [LICENSE](./LICENSE) for details.
