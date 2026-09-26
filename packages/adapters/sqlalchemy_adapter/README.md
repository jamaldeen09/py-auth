# py-auth-sqlalchemy

Async SQLAlchemy adapter for [`py-auth-core`](https://pypi.org/project/py-auth-core/).

You bring your own SQLAlchemy models and an `AsyncEngine`. The adapter implements the py-auth storage contract: users, linked accounts, and sessions. Integrity errors are mapped to `py-auth-core` exceptions (`DuplicateEntryError`, `ForeignKeyViolationError`, and so on).

Requires Python 3.10+ and SQLAlchemy 2.0+.

## Install

```bash
pip install py-auth-sqlalchemy
```

Install an async driver as well:

| Database   | Driver     | Example URL |
| ---------- | ---------- | ----------- |
| PostgreSQL | `asyncpg`  | `postgresql+asyncpg://...` |
| MySQL      | `aiomysql` | `mysql+aiomysql://...` |
| SQLite     | `aiosqlite`| `sqlite+aiosqlite:///...` |

```bash
pip install asyncpg    # or aiomysql, or aiosqlite
```

A sync engine is rejected. Only those three drivers are accepted.

## Models

Pass your own SQLAlchemy declarative classes. On construction, the adapter checks that each provided model **defines the columns py-auth reads and writes internally**. That check is about **whether the column exists**, not about database constraints.

`nullable`, `unique`, `ForeignKey`, defaults, indexes, and extra columns are yours. You can make `email` unique or not, `name` nullable or not, and so on. The adapter does not inspect those.

If a required column is missing (for example a `Session` model with no `session_token_hash`), `validate_sqlalchemy_model` raises `AdapterError` immediately. py-auth looks those attributes up by name; without them, later operations would fail unpredictably.

**Session** is always required. **User** and **Account** are optional on the adapter; omit them if you do not need user or OAuth-account operations. Calling those methods without the matching model also raises `AdapterError`. Extra columns beyond the lists below are allowed.

| Model | When you pass it | Required column *names* |
| --- | --- | --- |
| Session | Always | `id`, `session_token_hash`, `user_id`, `expires` |
| User | User CRUD / credentials | `id`, `email`, `name`, `image`, `password_hash` |
| Account | OAuth account linking | `id`, `user_id`, `type`, `provider`, `provider_account_id`, `access_token`, `refresh_token`, `expires_at`, `token_type`, `scope`, `id_token`, `session_state` |

Use `UTCDateTime` for `expires` so values stay timezone-aware UTC across backends. Naive datetimes are rejected. Constraints in the example below (`unique=True`, `nullable=...`) are typical choices, not adapter rules.

```python
from uuid import uuid4
from datetime import datetime
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from py_auth_sqlalchemy import UTCDateTime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid4()))
    session_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), ForeignKey("users.id"), nullable=False)
    expires: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(nullable=True)
    expires_at: Mapped[int | None] = mapped_column(nullable=True)
    token_type: Mapped[str | None] = mapped_column(nullable=True)
    scope: Mapped[str | None] = mapped_column(nullable=True)
    id_token: Mapped[str | None] = mapped_column(nullable=True)
    session_state: Mapped[str | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_accounts_provider_account"),
    )
```

## Usage

```python
from sqlalchemy.ext.asyncio import create_async_engine
from py_auth import PyAuth
from py_auth_sqlalchemy import SqlAlchemyAdapter

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")

adapter = SqlAlchemyAdapter(
    engine=engine,
    session_model=Session,
    user_model=User,
    account_model=Account,
)

auth = PyAuth(adapter=adapter, providers=[...])
```

Rows come back as dicts keyed by column name. Create the tables yourself (`Base.metadata.create_all` or Alembic); this package does not run migrations.

## License

MIT
