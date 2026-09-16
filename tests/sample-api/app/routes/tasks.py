from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import auth_router
from ..database import get_db
from ..models import Task
from ..schemas import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ---------------------------------------------------------------------------
# Every endpoint below requires an active py-auth session.
# The `session` dict contains at minimum: id, user_id, expires, csrf_token.
# ---------------------------------------------------------------------------


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    session=Depends(auth_router.get_current_session()),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task for the authenticated user."""
    task = Task(
        title=body.title,
        description=body.description or "",
        user_id=session["user_id"],
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    return TaskResponse.model_validate(task)


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    session=Depends(auth_router.get_current_session()),
    db: AsyncSession = Depends(get_db),
):
    """List all tasks belonging to the authenticated user."""
    stmt = (
        select(Task)
        .where(Task.user_id == session["user_id"])
        .order_by(Task.created_at.desc())
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    session=Depends(auth_router.get_current_session()),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific task by ID (must belong to the authenticated user)."""
    stmt = select(Task).where(Task.id == task_id, Task.user_id == session["user_id"])
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    return TaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    body: TaskUpdate,
    session=Depends(auth_router.get_current_session()),
    db: AsyncSession = Depends(get_db),
):
    """Update a task's title, description, or completed status."""
    stmt = select(Task).where(Task.id == task_id, Task.user_id == session["user_id"])
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    session=Depends(auth_router.get_current_session()),
    db: AsyncSession = Depends(get_db),
):
    """Delete a task by ID (must belong to the authenticated user)."""
    stmt = select(Task).where(Task.id == task_id, Task.user_id == session["user_id"])
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    await db.delete(task)
    await db.commit()
