# py-auth Sample API — Task Manager

A ready-to-run **Task Manager CRUD API** demonstrating all three `py-auth` packages working together:

| Package | Role in this sample |
|---|---|
| `py-auth-core` | Orchestrates session lifecycle, credential validation, CSRF protection |
| `py-auth-sqlalchemy` | Persists auth sessions in SQLite via async SQLAlchemy 2.0 |
| `py-auth-fastapi` | Mounts `/auth/signin`, `/auth/signout`, `/auth/session` routes automatically |

## Quick Start

```bash
# 1. Navigate to this directory
cd tests/sample-api

# 2. Create a virtual environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
 
# 4. Run the server
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive Swagger UI.

## API Endpoints

### Authentication (py-auth)

| Method | Path | Description |
|---|---|---|
| `POST` | `/register` | Create a new user account |
| `POST` | `/auth/signin` | Sign in with email & password (sets session cookies) |
| `POST` | `/auth/signout` | Sign out (requires active session) |
| `GET` | `/auth/session` | Verify active session & rotate CSRF token |

### Tasks (CRUD — protected)

All task endpoints require an active session (cookies set by `/auth/signin`).

| Method | Path | Description |
|---|---|---|
| `POST` | `/tasks/` | Create a new task |
| `GET` | `/tasks/` | List all your tasks |
| `GET` | `/tasks/{id}` | Get a specific task |
| `PUT` | `/tasks/{id}` | Update a task |
| `DELETE` | `/tasks/{id}` | Delete a task |

## Example Flow (curl)

```bash
# 1. Register a user
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "supersecret"}'

# 2. Sign in (save cookies)
curl -X POST http://127.0.0.1:8000/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "supersecret"}' \
  -c cookies.txt

# 3. Create a task (with session cookies)
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn py-auth", "description": "Read the docs and build something!"}' \
  -b cookies.txt

# 4. List tasks
curl http://127.0.0.1:8000/tasks/ -b cookies.txt

# 5. Sign out
curl -X POST http://127.0.0.1:8000/auth/signout -b cookies.txt
```

## Project Structure

```
sample-api/
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── main.py          # FastAPI app + lifespan
    ├── config.py        # DATABASE_URL setting
    ├── database.py      # Async engine + session factory
    ├── models.py        # User, AuthSession, Task ORM models
    ├── schemas.py       # Pydantic request/response schemas
    ├── auth.py          # py-auth wiring + registration
    └── routes/
        ├── __init__.py
        └── tasks.py     # Protected CRUD endpoints
```
