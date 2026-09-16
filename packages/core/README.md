# py-auth-core

Core authentication primitives and provider framework for the **py-auth**
ecosystem. Framework- and storage-agnostic: plug in any adapter that satisfies
[`PyAuthAdapterProtocol`](./src/py_auth/schemas.py) and any provider that
extends [`BaseProvider`](./src/py_auth/base.py).

## Features

- **Session lifecycle** — `PyAuth` creates, verifies, expires, and deletes
  sessions with hashed session tokens (SHA-256) and constant-time CSRF checks.
- **CSRF protection** — double-submit cookie validation with optional
  one-time rotation (`PyAuth.rotate_csrf()`).
- **Credentials provider** — Pydantic-validated sign-in bodies with a
  sync *or* async `authorize()` callback of your own.
- **Cookie configuration** — merge per-cookie options (name, `HttpOnly`,
  `SameSite`, `Secure`, `Max-Age`, path, domain) over secure defaults.
- **No framework, no ORM** — the adapter protocol keeps storage and web
  framework decisions in your application. Official companions:
  [`py-auth-sqlalchemy`](https://github.com/jamaldeen09/py-auth/tree/main/packages/adapters/sqlalchemy-adapter)
  and
  [`py-auth-fastapi`](https://github.com/jamaldeen09/py-auth/tree/main/packages/integrations/fastapi-integration).

## Installation

```bash
pip install py-auth-core
```

Optional database drivers for the SQLAlchemy adapter:

```bash
pip install "py-auth-core[sqlite]"     # aiosqlite
pip install "py-auth-core[postgres]"   # asyncpg
pip install "py-auth-core[mysql]"      # aiomysql
```

## Quickstart

```python
from py_auth import PyAuth, CredentialsProvider
from pydantic import BaseModel

class Login(BaseModel):
    email: str
    password: str

async def authorize(credentials: dict) -> dict | None:
    # ... look up the user, verify the password ...
    return {"id": user.id, "email": user.email}

auth = PyAuth(
    adapter=my_adapter,  # implements PyAuthAdapterProtocol
    providers=[CredentialsProvider(model=Login, authorize=authorize)],
)

result = await auth.signin_with_credentials({"email": "e@x.io", "password": "s3cret"})
assert result["error"] is None
token, csrf = result["data"]["session_token"], result["data"]["csrf_token"]

verified = await auth.verify_session(token, csrf)
assert verified["error"] is None
```

## License

MIT