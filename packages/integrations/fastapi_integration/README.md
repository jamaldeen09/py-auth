# py-auth-fastapi

FastAPI integration for [`py-auth-core`](https://pypi.org/project/py-auth-core/).

`PyAuthFastAPI` is an `APIRouter`. You pass it a configured `PyAuth` instance; it registers the HTTP routes, sets and clears cookies, and turns py-auth errors into FastAPI `HTTPException`s. It does not talk to the database — that stays on your adapter.

Requires Python 3.10+.

## Install

```bash
pip install py-auth-fastapi
```

You also need [`py-auth-core`](https://pypi.org/project/py-auth-core/) and a storage adapter such as [`py-auth-sqlalchemy`](https://pypi.org/project/py-auth-sqlalchemy/).

## Quick start

```python
from fastapi import FastAPI, Depends
from py_auth import PyAuth
from py_auth_fastapi import PyAuthFastAPI

auth = PyAuth(adapter=adapter, providers=[...])

app = FastAPI()
auth_router = PyAuthFastAPI(auth)
app.include_router(auth_router)

@app.get("/protected")
async def protected(session=Depends(auth_router.get_current_session())):
    return {"user_id": session["user_id"]}
```

Defaults: prefix `/auth`, tags `["Authentication"]`. Extra keyword arguments are forwarded to `APIRouter`. Cookie names and flags come from `auth.cookies` (configured on `PyAuth`, not here).

```python
PyAuthFastAPI(auth, prefix="/api/auth", tags=["Auth"])
```

## Routes

| Method | Path | CSRF | What it does |
| --- | --- | --- | --- |
| `GET` | `/auth/csrf` | No | Returns a CSRF token. Sets the CSRF cookie if it is missing. |
| `POST` | `/auth/signin/credentials` | Yes | JSON body → `signin_with_credentials`. Sets the session cookie. |
| `POST` | `/auth/signout` | Yes | Deletes the session, then clears session and CSRF cookies. |
| `GET` | `/auth/session` | No | Returns `id`, `user_id`, and `expires` for the current session. |
| `GET` | `/auth/signin/google` | No | Redirects to Google. Stores `state`, PKCE verifier, and `nonce` in cookies. Requires `GoogleProvider`. |
| `GET` | `/auth/google/callback` | No | Finishes Google sign-in, clears OAuth cookies, sets the session cookie. |

Mutating routes that require CSRF compare the CSRF **cookie** with the `x-csrf-token` **header** (double-submit). Fetch `GET /auth/csrf` first, then send the same value in that header.

On failure, the response looks like:

```json
{
  "detail": {
    "success": false,
    "message": "...",
    "error": { "status_code": 401, "code": "InvalidSession", "details": {} }
  }
}
```

## Protecting your own routes

`get_current_session()` is a FastAPI dependency factory. It reads the session cookie, calls `verify_session`, and injects the session dict (`id`, `user_id`, `expires`, …). Invalid or missing sessions become HTTP errors.

Use `add_csrf_verification=True` on endpoints that change state:

```python
@app.post("/profile")
async def update_profile(
    session=Depends(auth_router.get_current_session(add_csrf_verification=True)),
):
    ...
```

`verify_csrf()` is available on its own if you only need the CSRF check.

## License

MIT
