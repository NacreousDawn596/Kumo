"""Project routes (lightweight workspaces)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Project, ProjectMember, User
from app.security.authz import is_group_member
from app.security.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str
    description: str | None = None
    group_id: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    archived: bool | None = None


def _out(p: Project) -> dict:
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "owner_id": p.owner_id, "group_id": p.group_id,
        "archived": p.archived_at is not None,
        "created_at": p.created_at, "updated_at": p.updated_at,
    }


def _can_view(db: Session, user: User, p: Project) -> bool:
    if p.owner_id == user.id:
        return True
    if p.group_id and is_group_member(db, user.id, p.group_id):
        return True
    row = db.execute(select(ProjectMember).where(ProjectMember.project_id == p.id, ProjectMember.user_id == user.id)).scalar_one_or_none()
    return row is not None


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mine = db.execute(select(Project).where(Project.owner_id == user.id)).scalars().all()
    shared = db.execute(
        select(Project).join(ProjectMember, ProjectMember.project_id == Project.id).where(ProjectMember.user_id == user.id)
    ).scalars().all()
    projects = {p.id: p for p in list(mine) + list(shared)}
    return [_out(p) for p in projects.values()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.group_id and not is_group_member(db, user.id, body.group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    project = Project(name=body.name, description=body.description, owner_id=user.id, group_id=body.group_id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(project)
    return _out(project)


@router.get("/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None or not _can_view(db, user, project):
        raise HTTPException(status_code=404, detail="Project not found")
    return _out(project)


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    data = body.model_dump(exclude_unset=True)
    if "archived" in data:
        from app.models import utcnow
        project.archived_at = utcnow() if data.pop("archived") else None
    for key, value in data.items():
        if value is not None:
            setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return _out(project)
