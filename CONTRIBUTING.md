# Contributing

Bug reports, design discussion, and pull requests are welcome. This repo is a **monorepo of three publishable packages**. Keep changes scoped to the package they belong to.

| Path | PyPI name | Import |
| --- | --- | --- |
| `packages/core` | `py-auth-core` | `py_auth` |
| `packages/adapters/sqlalchemy_adapter` | `py-auth-sqlalchemy` | `py_auth_sqlalchemy` |
| `packages/integrations/fastapi_integration` | `py-auth-fastapi` | `py_auth_fastapi` |

Core must not import FastAPI or SQLAlchemy. The adapter must not register HTTP routes. The FastAPI package must not talk to a database. If a change needs all three layers, split it into clear commits (or PRs) rather than smuggling SQL into `py_auth`.

Package READMEs are what appear on PyPI. Keep them self-contained (no “see CONTRIBUTING.md”). The root [README.md](README.md) is the GitHub overview.

Requires **Python 3.10+**.

## Setup

```bash
git clone https://github.com/jamaldeen09/py-auth.git
cd py-auth
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e packages/core
pip install -e packages/adapters/sqlalchemy_adapter
pip install -e packages/integrations/fastapi_integration
pip install pytest pytest-asyncio python-dotenv
pip install asyncpg aiosqlite aiomysql   # adapter tests, whichever backends you run
```

Editable installs pick up edits under `packages/*/src` without reinstalling.

Do not commit `.env`, virtualenvs, or secrets (see `.gitignore`).

## Tests

Pytest config lives in the root `pyproject.toml` (`asyncio_mode = strict`, session-scoped event loop). Run from the repository root.

```bash
pytest tests/core
pytest tests/integrations/fastapi_integration
pytest tests/adapters/sqlalchemy_adapter
pytest
```

| Suite | Needs a database? | Notes |
| --- | --- | --- |
| `tests/core` | No | `PyAuth` and providers against a mocked adapter |
| `tests/integrations/fastapi_integration` | No | Router, cookies, dependencies against a mocked `PyAuth` |
| `tests/adapters/sqlalchemy_adapter` | Yes | Real `AsyncEngine`; URL from `TEST_DATABASE_URL` |

Adapter tests create tables for the session, then wipe rows after each test. Supported URLs match the adapter: `postgresql+asyncpg://…`, `mysql+aiomysql://…`, `sqlite+aiosqlite://…`.

Example `.env` (loaded via `python-dotenv`):

```bash
TEST_DATABASE_URL=sqlite+aiosqlite:///./test.db
```

Against Compose (see below):

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@127.0.0.1:5433/postgres
# or
TEST_DATABASE_URL=mysql+aiomysql://root:PASSWORD@127.0.0.1:3307/YOUR_DB
```

Core and FastAPI tests should stay green without Docker. If you change persistence, run the adapter suite on at least one backend; Postgres is the usual one.

## Docker Compose

[`compose.yml`](compose.yml) is split on purpose:

- `fastapi-app` + `app-postgres` — demo only ([`examples/fastapi_app`](examples/fastapi_app))
- `test-postgres` (host **5433** by default) and `test-mysql` (host **3307**) — tests only

```bash
docker compose up -d test-postgres   # and/or test-mysql
```

Passwords and ports come from `.env`: `TEST_POSTGRES_PASSWORD`, `TEST_POSTGRES_PORT`, `TEST_MYSQL_ROOT_PASSWORD`, `TEST_MYSQL_DATABASE`, `TEST_MYSQL_PORT`. Demo app vars (`DATABASE_URL`, `APP_POSTGRES_*`, Google client settings) are unrelated to the test suite.

## Example app

[`examples/fastapi_app`](examples/fastapi_app) is a consumer of the published APIs, not a fourth package. Use it to sanity-check credentials + Google + CSRF, not as a substitute for pytest.

## What we will merge

- **Bugs** with a failing test or a short repro.
- **Features** that respect the boundaries above. New provider → `packages/core`. New store → new adapter package (or extend SQLAlchemy without breaking column-name validation). New framework → new integration, same pattern as FastAPI.
- **Docs** that match the code. If you change a route, a required column name, or an exception, update the relevant README in the same PR.

`PyAuthAdapterProtocol` is a contract. Adding or renaming a method means every adapter and the mock adapter in `tests/core/conftest.py` must follow. Same for required SQLAlchemy column *names*: they are not the same as `nullable` / `unique`; do not relax that check without a deliberate, documented change.

Prefer small PRs. Match the style of the file you are in (no new formatter/linter mandate). Do not bump package versions in `pyproject.toml` unless a maintainer asks — releases are separate from feature work.

## Issues

Use GitHub issues for bugs and proposals. For bugs, include Python version, package versions (`py-auth-core` / `sqlalchemy` / `fastapi`), and what you expected vs what happened. For protocol or security-sensitive changes, open an issue before a large PR.

## License

By contributing, you agree that your work is licensed under the same MIT license as the rest of the project ([LICENSE](LICENSE)).
