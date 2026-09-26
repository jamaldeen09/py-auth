import os
from typing import Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv, find_dotenv

from sqlalchemy.ext.asyncio import create_async_engine
from py_auth import PyAuth
from py_auth.providers import CredentialsProvider, GoogleProvider
from py_auth_sqlalchemy import SqlAlchemyAdapter
from py_auth_fastapi import PyAuthFastAPI

from .models import Session, User, Account, Base
from .utils import hash_password, verify_password

# Load environment variables from .env file
load_dotenv(find_dotenv()) 

database_url = os.getenv("DATABASE_URL")
google_client_id = os.getenv("GOOGLE_CLIENT_ID")
google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

# Initialize the asynchronous database engine and adapter for py_auth
engine = create_async_engine(database_url, echo=True)
adapter = SqlAlchemyAdapter(
    engine=engine, 
    session_model=Session,  
    account_model=Account, 
    user_model=User
)

# Pydantic schema for validating incoming credential login payloads
class LoginSchema(BaseModel):
    email: EmailStr
    name: str
    image: str | None = None
    password: str

# Custom authorization logic: handles user registration on first login and password validation thereafter
async def authorize(credentials: Dict[str, Any]):
    email = credentials["email"]
    name = credentials["name"]
    password = credentials["password"]

    user = await adapter.get_user_by_email(email)

    # If the user doesn't exist, create a new record with a hashed password
    if not user:
        password_hash = hash_password(password)
        return await adapter.create_user({
            "email": email,
            "name": name,
            "image": credentials.get("image"),
            "password_hash": password_hash
        })
    
    # If user exists, verify their password against the stored hash
    is_password_valid = verify_password(password=password, hashed_password=user["password_hash"])
    if not is_password_valid:
        return None
    
    return user

# Set up authentication providers
credentials_provider = CredentialsProvider(model=LoginSchema, authorize=authorize)
google_provider = GoogleProvider(
    client_id=google_client_id,
    client_secret=google_client_secret,
    redirect_uri=google_redirect_uri
)

# Instantiate core PyAuth manager
auth = PyAuth(adapter=adapter, providers=[credentials_provider, google_provider])

# Helper function to auto-create database tables on startup using models inheriting from Base
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# FastAPI lifespan manager to handle startup tasks (like creating tables)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

# Initialize FastAPI app and attach authentication routers
app = FastAPI(lifespan=lifespan)
auth_router = PyAuthFastAPI(auth)
app.include_router(auth_router)

# Example protected route requiring a valid active session
@app.get("/protected-route")
def protected_route(session = Depends(auth_router.get_current_session())):
    return {"success": True, "session": session}