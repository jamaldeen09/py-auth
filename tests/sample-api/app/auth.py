import bcrypt

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from py_auth import PyAuth, CredentialsProvider
from py_auth_sqlalchemy import SqlAlchemyAdapter
from py_auth_fastapi import PyAuthFastAPI

from .database import engine, async_session_maker
from .models import Session, User
from .schemas import LoginSchema, RegisterSchema, UserResponse


# ---------------------------------------------------------------------------
# 1. Database adapter — tells py-auth how to persist sessions
# ---------------------------------------------------------------------------
adapter = SqlAlchemyAdapter(engine=engine, session_model=Session)


# ---------------------------------------------------------------------------
# 2. Authorize callback — verifies credentials against the User table
# ---------------------------------------------------------------------------
async def authorize(credentials: dict) -> dict | None:
    """
    Look up the user by email. If the user does not exist, create them.
    If the user exists, verify the bcrypt password hash.
    Returns a user dict on success, or None on password mismatch.
    """
    async with async_session_maker() as session:
        stmt = select(User).where(User.email == credentials["email"])
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            # Create the user if they don't exist
            password_bytes = credentials["password"].encode("utf-8")
            hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
            
            user = User(
                email=credentials["email"],
                hashed_password=hashed_password
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Verify password for existing user
            password_bytes = credentials["password"].encode("utf-8")
            if not bcrypt.checkpw(password_bytes, user.hashed_password.encode("utf-8")):
                return None

    return {"id": user.id, "email": user.email}


# ---------------------------------------------------------------------------
# 3. Credentials provider — validates the login body via Pydantic, then
#    delegates to the authorize() callback above
# ---------------------------------------------------------------------------
credentials_provider = CredentialsProvider(
    model=LoginSchema,
    authorize=authorize,
)


# ---------------------------------------------------------------------------
# 4. PyAuth core — orchestrates session lifecycle
# ---------------------------------------------------------------------------
auth = PyAuth(
    adapter=adapter,
    providers=[credentials_provider],
)


# ---------------------------------------------------------------------------
# 5. FastAPI integration — mounts /auth/signin, /auth/signout, /auth/session
# ---------------------------------------------------------------------------
auth_router = PyAuthFastAPI(auth)