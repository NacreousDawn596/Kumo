"""Message and conversation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=64000)
    reply_to_id: str | None = None
    link_resource_type: str | None = None
    link_resource_id: str | None = None


class MessagePatch(BaseModel):
    body: str = Field(min_length=1, max_length=64000)


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    body: str
    created_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    reply_to_id: str | None = None
    link_resource_type: str | None = None
    link_resource_id: str | None = None
    reactions: list[dict] = []


class ConversationOut(BaseModel):
    id: str
    kind: str
    title: str | None = None
    group_id: str | None = None
    other_user_ids: list[str] = []
    last_message: MessageOut | None = None
    unread_count: int = 0
    updated_at: datetime | None = None
