from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth import auth_router
from .database import engine
from .models import Base
from .routes.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all database tables on startup, dispose engine on shutdown."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Task Manager API — py-auth Sample",
    description=(
        "A sample CRUD API demonstrating py-auth-core, py-auth-fastapi, "
        "and py-auth-sqlalchemy working together for session-based authentication."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Mount py-auth authentication routes  (POST /auth/signin, POST /auth/signout, GET /auth/session)
app.include_router(auth_router)

# Mount task CRUD routes  (POST/GET/PUT/DELETE /tasks/*)
app.include_router(tasks_router)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "success": True,
        "message": "Task Manager API is running. Visit /docs for interactive documentation.",
    }
