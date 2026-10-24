"""Task routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Task, User, utcnow
from app.security.authz import is_group_member
from app.security.deps import get_current_user
from app.tasks.schemas import TaskCreate, TaskOut, TaskPatch

router = APIRouter(prefix="/tasks", tags=["tasks"])

STATUSES = {"todo", "in_progress", "done", "cancelled"}


def _can_view(db: Session, user: User, task: Task) -> bool:
    if task.owner_id == user.id or task.assignee_id == user.id:
        return True
    if task.group_id and is_group_member(db, user.id, task.group_id):
        return True
    return False


def _out(task: Task) -> TaskOut:
    return TaskOut.model_validate(task)


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    group_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Task)
    if group_id:
        stmt = stmt.where(Task.group_id == group_id)
    elif project_id:
        stmt = stmt.where(Task.project_id == project_id)
    else:
        stmt = stmt.where((Task.owner_id == user.id) | (Task.assignee_id == user.id))
    if status:
        stmt = stmt.where(Task.status == status)
    tasks = db.execute(stmt.order_by(Task.created_at.desc())).scalars().all()
    return [_out(t) for t in tasks if _can_view(db, user, t)]


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.group_id and not is_group_member(db, user.id, body.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    task = Task(owner_id=user.id, **body.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return _out(task)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or not _can_view(db, user, task):
        raise HTTPException(status_code=404, detail="Task not found")
    return _out(task)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: str, body: TaskPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or not _can_view(db, user, task):
        raise HTTPException(status_code=404, detail="Task not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(task, key, value)
    if "status" in data and data["status"] == "done" and task.completed_at is None:
        task.completed_at = utcnow()
    elif "status" in data and data["status"] != "done":
        task.completed_at = None
    db.commit()
    db.refresh(task)
    return _out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return None
