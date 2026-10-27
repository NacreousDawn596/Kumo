"""Page and block HTTP routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Page, PageBlock, User
from app.pages import service
from app.pages.schemas import (
    BlockIn,
    BlockOut,
    BlockPatch,
    PageCreate,
    PageDetail,
    PageOut,
    PagePatch,
)
from app.security.authz import has_level, page_permission
from app.security.deps import get_current_user

router = APIRouter(prefix="/pages", tags=["pages"])


def _block_out(b: PageBlock) -> BlockOut:
    props = None
    if b.properties:
        try:
            props = json.loads(b.properties)
        except (ValueError, TypeError):
            props = None
    return BlockOut(
        id=b.id,
        block_type=b.block_type,
        content=b.content,
        properties=props,
        parent_block_id=b.parent_block_id,
        position=b.position,
        created_by=b.created_by,
    )


@router.post("", response_model=PageOut, status_code=status.HTTP_201_CREATED)
def create_page(body: PageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = service.create_page(
        db, user, title=body.title, parent_id=body.parent_id,
        icon=body.icon, group_id=body.group_id, template=body.template,
    )
    return service.serialize_page(db, page, "manage")


@router.get("", response_model=list[PageOut])
def list_pages(
    parent_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pages = service.list_pages(db, user, parent_id=parent_id)
    return [service.serialize_page(db, p, "manage") for p in pages]


@router.get("/{page_id}", response_model=PageDetail)
def get_page(page_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = service.require_page(db, user, page_id, "view")
    perm = page_permission(db, user, page)
    base = service.serialize_page(db, page, perm)
    base["blocks"] = [_block_out(b).model_dump() for b in service.get_blocks(page)]
    return base


@router.patch("/{page_id}", response_model=PageOut)
def update_page(page_id: str, body: PagePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = service.require_page(db, user, page_id, "edit")
    data = body.model_dump(exclude_unset=True)
    if "parent_id" in data and data["parent_id"] and data["parent_id"] != page.parent_id:
        service.require_page(db, user, data["parent_id"], "edit")
    for key, value in data.items():
        if key == "archived":
            page.is_archived = value
        elif value is not None:
            setattr(page, key, value)
    db.commit()
    db.refresh(page)
    return service.serialize_page(db, page, page_permission(db, user, page))


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(page_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = service.require_page(db, user, page_id, "manage")
    page.is_archived = True
    db.commit()
    return None


@router.put("/{page_id}/blocks", response_model=list[BlockOut])
def put_blocks(
    page_id: str,
    blocks: list[BlockIn],
    expected_version: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = service.require_page(db, user, page_id, "edit")
    if expected_version is not None and expected_version != page.version:
        raise HTTPException(status_code=409, detail="Page was modified by someone else; refresh to merge.")
    result = service.update_blocks(db, page, [b.model_dump(exclude_unset=True) for b in blocks], user)
    db.commit()
    for b in result:
        db.refresh(b)
    return [_block_out(b) for b in result]


@router.post("/{page_id}/links", status_code=status.HTTP_201_CREATED)
def add_link(page_id: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = service.require_page(db, user, page_id, "edit")
    link = service.add_link(db, user, page, target_id=body.get("target_id", ""), context=body.get("context"))
    return {"id": link.id, "target_id": link.target_id}


@router.get("/{page_id}/backlinks")
def get_backlinks(page_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = service.require_page(db, user, page_id, "view")
    return service.backlinks(db, user, page)
