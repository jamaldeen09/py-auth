# py-auth-fastapi

**FastAPI integration for [py-auth](https://pypi.org/project/py-auth/).**

Removes the boilerplate of wiring `py-auth` authentication into a FastAPI application down to a single line.

[![PyPI version](https://img.shields.io/pypi/v/py-auth-fastapi.svg)](https://pypi.org/project/py-auth-fastapi/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-auth-fastapi.svg)](https://pypi.org/project/py-auth-fastapi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features

- ✅ **One-liner setup** — Mounts as a standard FastAPI `APIRouter` with `app.include_router()`
- ✅ **Automatic cookie handling** — Sets and clears session and CSRF cookies automatically
- ✅ **Dependency injection** — Includes `get_current_session()` dependency factory for protecting endpoints
- ✅ **Built-in error handling** — Converts `py-auth` errors into standard FastAPI `HTTPException` responses

---

## Installation

```bash
pip install py-auth-fastapi
```

---

## Quick Start

```python
from fastapi import FastAPI, Depends
from py_auth import PyAuth
from py_auth_fastapi import PyAuthFastAPI

# Initialize your PyAuth instance
auth = PyAuth(...)

app = FastAPI()

# Mount py-auth router
auth_router = PyAuthFastAPI(auth)
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Protect routes using the session dependency
@app.get("/protected")
async def protected_route(session=Depends(auth_router.get_current_session())):
    return {"message": f"Hello user {session['user_id']}"}
```

### Endpoints Registered

- `POST /auth/signin` — Authenticates credentials and sets session & CSRF cookies
- `POST /auth/signout` — Revokes session and deletes cookies
- `GET  /auth/session` — Fetches current session and rotates CSRF token

---

## License

[MIT](LICENSE)
