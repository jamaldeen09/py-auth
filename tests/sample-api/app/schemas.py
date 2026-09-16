import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------
class LoginSchema(BaseModel):
    """Schema used by py-auth's CredentialsProvider for sign-in validation."""
    email: EmailStr
    password: str


class RegisterSchema(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public user representation (never expose hashed_password)."""
    id: str
    email: str


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------
class TaskCreate(BaseModel):
    """Payload for creating a new task."""
    title: str
    description: Optional[str] = ""


class TaskUpdate(BaseModel):
    """Payload for updating an existing task — all fields optional."""
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


class TaskResponse(BaseModel):
    """Task data returned to the client."""
    id: str
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
