"""Knowledge routes: graph, search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import File, Group, GroupMember, Page, Task, User
from app.pages import service as page_service
from app.security.authz import file_permission, page_permission
from app.security.deps import get_current_user

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/graph")
def graph(
    page_id: str | None = None,
    depth: int = Query(default=2, ge=1, le=5),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return page_service.build_graph(db, user, page_id=page_id, depth=depth)


@router.get("/search")
def search(
    q: str = Query(min_length=1, max_length=200),
    kind: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    like = f"%{q.lower()}%"
    results: list[dict] = []

    if kind in (None, "page"):
        pages = db.execute(
            select(Page).where(
                Page.is_archived.is_(False), Page.title.ilike(like)
            ).limit(limit)
        ).scalars().all()
        for p in pages:
            if page_permission(db, user, p) is None:
                continue
            results.append({"type": "page", "id": p.id, "title": p.title, "snippet": None})

    if kind in (None, "file"):
        files = db.execute(
            select(File).where(File.name.ilike(like), File.is_folder.is_(False)).limit(limit)
        ).scalars().all()
        for f in files:
            if file_permission(db, user, f) is None:
                continue
            results.append({"type": "file", "id": f.id, "title": f.name, "snippet": f.mime_type})

    if kind in (None, "task"):
        tasks = db.execute(
            select(Task).where(Task.title.ilike(like)).limit(limit)
        ).scalars().all()
        for t in tasks:
            if t.owner_id != user.id:
                continue
            results.append({"type": "task", "id": t.id, "title": t.title, "snippet": t.status})

    if kind in (None, "group"):
        my_group_ids = [g.group_id for g in db.execute(
            select(GroupMember).where(GroupMember.user_id == user.id)
        ).scalars()]
        groups = db.execute(
            select(Group).where(Group.id.in_(my_group_ids), Group.name.ilike(like)).limit(limit)
        ).scalars().all()
        for g in groups:
            results.append({"type": "group", "id": g.id, "title": g.name, "snippet": None})

    return results[:limit]
