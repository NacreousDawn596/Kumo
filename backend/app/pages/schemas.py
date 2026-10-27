"""Page and block schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BlockIn(BaseModel):
    block_type: str
    content: str | None = None
    properties: dict | None = None
    parent_block_id: str | None = None
    position: int = 0


class BlockOut(BaseModel):
    id: str
    block_type: str
    content: str | None = None
    properties: dict | None = None
    parent_block_id: str | None = None
    position: int
    created_by: str


class BlockPatch(BaseModel):
    content: str | None = None
    properties: dict | None = None
    block_type: str | None = None
    deleted: bool | None = None


class PageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None
    icon: str | None = None
    group_id: str | None = None
    template: str | None = None


class PagePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    icon: str | None = None
    parent_id: str | None = None
    archived: bool | None = None


class PageOut(BaseModel):
    id: str
    title: str
    icon: str | None = None
    parent_id: str | None = None
    owner_id: str
    group_id: str | None = None
    created_at: datetime
    updated_at: datetime
    permission: str | None = None
    has_children: bool = False
    version: int = 0


class PageDetail(PageOut):
    blocks: list[BlockOut] = []


class LinkCreate(BaseModel):
    target_id: str
    target_type: str = "page"
    context: str | None = None


class BacklinkOut(BaseModel):
    source_id: str
    source_title: str
    source_type: str
    context: str | None = None
    created_at: datetime


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
