"""Vault schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    mime_type: str
    size_bytes: int
    is_folder: bool
    previewable: bool
    owner_id: str
    group_id: str | None = None
    created_at: datetime
    updated_at: datetime
    permission: str | None = None
    is_linked: bool = False


class FilePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_folder: str | None = None


class ShareIn(BaseModel):
    target_type: str  # user|group|session
    target_id: str
    permission: str = "view"


class FileCommentIn(BaseModel):
    body: str
    page_number: int | None = None
    anchor: str | None = None
    reply_to_id: str | None = None


class FileCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    author_id: str
    body: str
    page_number: int | None = None
    anchor: str | None = None
    reply_to_id: str | None = None
    created_at: datetime
