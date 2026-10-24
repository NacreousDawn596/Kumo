"""Page service: authorization-aware CRUD and link/graph logic."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Page,
    PageBlock,
    PageLink,
    PagePermission,
    PageRevision,
    User,
)
from app.security.authz import has_level, page_permission

# Starter templates: mapping of template name -> list of (block_type, content).
TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "lecture_notes": [
        ("heading", "Lecture title"),
        ("paragraph", "Date, course, and lecturer."),
        ("heading", "Key points"),
        ("bullet", "Point one"),
        ("bullet", "Point two"),
        ("heading", "Notes"),
        ("paragraph", ""),
    ],
    "course_page": [
        ("heading", "Course overview"),
        ("paragraph", "Instructor, schedule, and resources."),
        ("heading", "Chapters"),
        ("todo", "Chapter 1"),
        ("todo", "Chapter 2"),
    ],
    "meeting_notes": [
        ("heading", "Attendees"),
        ("paragraph", ""),
        ("heading", "Agenda"),
        ("bullet", ""),
        ("heading", "Decisions"),
        ("bullet", ""),
    ],
    "lab_report": [
        ("heading", "Objective"),
        ("paragraph", ""),
        ("heading", "Procedure"),
        ("paragraph", ""),
        ("heading", "Results"),
        ("paragraph", ""),
        ("heading", "Conclusion"),
        ("paragraph", ""),
    ],
    "study_session_notes": [
        ("heading", "Topic"),
        ("paragraph", ""),
        ("heading", "What I learned"),
        ("bullet", ""),
        ("heading", "Questions"),
        ("bullet", ""),
    ],
}


def require_page(db: Session, user: User, page_id: str, required: str = "view") -> Page:
    page = db.get(Page, page_id)
    if page is None or page.is_archived:

        raise HTTPException(status_code=404, detail="Page not found")
    perm = page_permission(db, user, page)
    if perm is None or not has_level(perm, required):

        raise HTTPException(status_code=404, detail="Page not found")
    return page


def create_page(
    db: Session,
    user: User,
    *,
    title: str,
    parent_id: str | None,
    icon: str | None,
    group_id: str | None,
    template: str | None,
) -> Page:
    if parent_id:
        require_page(db, user, parent_id, "edit")
    if group_id:
        from app.security.authz import is_group_member

        if not is_group_member(db, user.id, group_id):

            raise HTTPException(status_code=403, detail="Not a member of this group")
    page = Page(
        title=title,
        parent_id=parent_id,
        icon=icon,
        owner_id=user.id,
        group_id=group_id,
    )
    db.add(page)
    db.flush()
    blocks = TEMPLATES.get(template or "", [("paragraph", "")])
    for i, (btype, content) in enumerate(blocks):
        db.add(PageBlock(page_id=page.id, block_type=btype, content=content, position=i, created_by=user.id))
    db.commit()
    db.refresh(page)
    return page


def serialize_page(db: Session, page: Page, perm: str | None) -> dict:
    has_children = db.execute(
        select(func.count()).select_from(Page).where(Page.parent_id == page.id, Page.is_archived.is_(False))
    ).scalar_one() > 0
    return {
        "id": page.id,
        "title": page.title,
        "icon": page.icon,
        "parent_id": page.parent_id,
        "owner_id": page.owner_id,
        "group_id": page.group_id,
        "created_at": page.created_at,
        "updated_at": page.updated_at,
        "permission": perm,
        "has_children": has_children,
    }


def list_pages(db: Session, user: User, *, parent_id: str | None = None, include_archived: bool = False) -> list[Page]:
    stmt = select(Page).where(Page.owner_id == user.id)
    if parent_id is None:
        stmt = stmt.where(Page.parent_id.is_(None))
    else:
        stmt = stmt.where(Page.parent_id == parent_id)
    if not include_archived:
        stmt = stmt.where(Page.is_archived.is_(False))
    return list(db.execute(stmt.order_by(Page.updated_at.desc())).scalars())


def update_blocks(db: Session, page: Page, blocks: list[dict], user: User) -> list[PageBlock]:
    """Apply a client-supplied ordered list of blocks (create/update/delete).

    Uses stable block IDs and explicit per-block operations. Deleted blocks are
    soft-deleted rather than removed, keeping history intact.
    """
    existing = {b.id: b for b in page.blocks if not b.deleted}
    result: list[PageBlock] = []
    for i, item in enumerate(blocks):
        bid = item.get("id")
        if bid and bid in existing:
            block = existing[bid]
            if "block_type" in item:
                block.block_type = item["block_type"]
            if "content" in item:
                block.content = item["content"]
            if "properties" in item:
                block.properties = json.dumps(item["properties"]) if item["properties"] is not None else None
            if "parent_block_id" in item:
                block.parent_block_id = item["parent_block_id"]
            block.position = i
            block.deleted = False
            result.append(block)
        else:
            block = PageBlock(
                page_id=page.id,
                block_type=item.get("block_type", "paragraph"),
                content=item.get("content"),
                properties=json.dumps(item["properties"]) if item.get("properties") else None,
                parent_block_id=item.get("parent_block_id"),
                position=i,
                created_by=user.id,
            )
            db.add(block)
            result.append(block)
    # Soft-delete blocks not present in the new list.
    new_ids = {b.id for b in result}
    for bid, block in existing.items():
        if bid not in new_ids:
            block.deleted = True
    return result


def get_blocks(page: Page) -> list[PageBlock]:
    return [b for b in page.blocks if not b.deleted]


def add_link(db: Session, user: User, page: Page, *, target_id: str, context: str | None) -> PageLink:
    target = db.get(Page, target_id)
    if target is None:

        raise HTTPException(status_code=404, detail="Target not found")
    # Verify the user can at least view the target.
    require_page(db, user, target_id, "view")
    link = PageLink(source_id=page.id, target_id=target_id, context=context)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def backlinks(db: Session, user: User, page: Page) -> list[dict]:
    rows = db.execute(
        select(PageLink, Page)
        .join(Page, Page.id == PageLink.source_id)
        .where(PageLink.target_id == page.id)
    ).all()
    out = []
    for link, source in rows:
        if source is None:
            continue
        # Only reveal backlinks the user can access.
        perm = page_permission(db, user, source)
        if perm is None:
            continue
        out.append(
            {
                "source_id": source.id,
                "source_title": source.title,
                "source_type": "page",
                "context": link.context,
                "created_at": link.created_at,
            }
        )
    return out


def build_graph(db: Session, user: User, *, page_id: str | None = None, depth: int = 2) -> dict:
    """Build a graph of authorized pages and their links."""
    from collections import deque

    start_ids: list[str]
    if page_id:
        start_ids = [page_id]
    else:
        start_ids = [p.id for p in db.execute(select(Page).where(Page.owner_id == user.id)).scalars()]

    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque((pid, 0) for pid in start_ids)
    pages: dict[str, Page] = {}
    while queue:
        pid, d = queue.popleft()
        if pid in seen or d > depth:
            continue
        seen.add(pid)
        page = db.get(Page, pid)
        if page is None or page.is_archived:
            continue
        if page_permission(db, user, page) is None:
            continue
        pages[pid] = page

    edges: list[dict] = []
    for pid in list(pages.keys()):
        for link in db.execute(select(PageLink).where(PageLink.source_id == pid)).scalars():
            if link.target_id in pages:
                edges.append({"source": pid, "target": link.target_id, "label": "links"})
            else:
                # Add the target as a leaf if authorized.
                tgt = db.get(Page, link.target_id)
                if tgt and not tgt.is_archived and page_permission(db, user, tgt) is not None:
                    pages[tgt.id] = tgt
                    edges.append({"source": pid, "target": tgt.id, "label": "links"})

    nodes = [
        {"id": p.id, "label": p.title, "kind": "page"}
        for p in pages.values()
    ]
    return {"nodes": nodes, "edges": edges}
