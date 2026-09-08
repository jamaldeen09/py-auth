# py-auth

**Modular, framework-agnostic authentication ecosystem for Python backends.**

`py-auth` provides secure session management, credential-based authentication, CSRF double-submit protection, and a clean provider/adapter architecture without tying your application to a specific database, ORM, or web framework.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python versions](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

---

## Ecosystem Packages

The project is architected as a modular monorepo:

| Package | Directory | PyPI | Description |
|---|---|---|---|
| **`py-auth-core`** | [`packages/core`](./packages/core) | [![PyPI](https://img.shields.io/pypi/v/py-auth-core.svg)](https://pypi.org/project/py-auth-core/) | Core auth engine, credentials provider, session protocol, and security primitives. |
| **`py-auth-sqlalchemy`** | [`packages/adapters/sqlalchemy-adapter`](./packages/adapters/sqlalchemy-adapter) | [![PyPI](https://img.shields.io/pypi/v/py-auth-sqlalchemy.svg)](https://pypi.org/project/py-auth-sqlalchemy/) | High-performance async SQLAlchemy 2.0 adapter for PostgreSQL, MySQL, and SQLite. |
| **`py-auth-fastapi`** | [`packages/integrations/fastapi-integration`](./packages/integrations/fastapi-integration) | [![PyPI](https://img.shields.io/pypi/v/py-auth-fastapi.svg)](https://pypi.org/project/py-auth-fastapi/) | Drop-in FastAPI `APIRouter` integration with route protection dependency. |

---

## Installation

Install the core package along with the adapter and integration for your stack:

```bash
# Core authentication primitives
pip install py-auth-core

# Optional: Async SQLAlchemy 2.0 adapter
pip install py-auth-sqlalchemy

# Optional: FastAPI integration
pip install py-auth-fastapi
```

---

## Quickstart (FastAPI + SQLAlchemy)

Here is how the packages seamlessly connect together in a single application:

```python
import datetime, uuid
from fastapi import FastAPI, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from py_auth import PyAuth, CredentialsProvider
from py_auth_sqlalchemy import SqlAlchemyAdapter
from py_auth_fastapi import PyAuthFastAPI

# 1. Define your SQLAlchemy Session model
class Base(AsyncAttrs, DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    expires: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

# 2. Configure the database adapter
engine = create_async_engine("sqlite+aiosqlite:///auth.db")
adapter = SqlAlchemyAdapter(engine=engine, session_model=Session)

# 3. Define credentials validation & authorization callback
class LoginSchema(BaseModel):
    email: EmailStr
    password: str

async def authorize(credentials: dict) -> dict | None:
    # Verify user against your user database/table (e.g. check password hash)
    if credentials.get("email") == "user@example.com" and credentials.get("password") == "secret123":
        return {"id": "user_123", "email": "user@example.com"}
    return None

credentials_provider = CredentialsProvider(model=LoginSchema, authorize=authorize)

# 4. Initialize PyAuth
auth = PyAuth(adapter=adapter, providers=[credentials_provider])

# 5. Mount FastAPI routes (mounts /auth/* routes automatically)
app = FastAPI()
auth_router = PyAuthFastAPI(auth)
app.include_router(auth_router)

# 6. Protect private endpoints
@app.get("/me")
async def get_me(session=Depends(auth_router.get_current_session())):
    return {"message": "Authenticated", "session": session}
```

### Endpoints Mounted Automatically

- `POST /auth/signin` — Validates credentials, persists session, and sets `session_token` and `csrf_token` cookies.
- `POST /auth/signout` — Revokes session in database and clears auth cookies.
- `GET  /auth/session` — Verifies active session, rotates the CSRF token, and returns active session data.

---

## Core Principles

- 🔒 **Secure by Default** — Uses cryptographically secure URL-safe tokens, SHA-256 token hashing at rest, HttpOnly cookies, SameSite enforcement, and automatic CSRF double-submit validation.
- ⚡ **Async-First** — Everything from database adapters to route endpoints is asynchronous and built for high-throughput Python services.
- 🧩 **Modular & Pluggable** — Implement `PyAuthAdapterProtocol` to add any storage backend (MongoDB, Redis, Tortoise ORM, etc.) or write new framework integrations without touching core logic.
- 🛡️ **Strict Runtime Validation** — Structural protocol checks and Pydantic validation catch misconfigurations at startup before serving any requests.

---

## Contributing

Contributions are welcome! Please check our [Contributing Guide](CONTRIBUTING.md) for details on creating adapters, integrations, and providers.

---

## License

This project is licensed under the [MIT License](LICENSE).
