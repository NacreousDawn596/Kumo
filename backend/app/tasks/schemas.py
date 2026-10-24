"""Task schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str = "todo"
    priority: str = "none"
    due_date: datetime | None = None
    start_date: datetime | None = None
    assignee_id: str | None = None
    project_id: str | None = None
    group_id: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    start_date: datetime | None = None
    assignee_id: str | None = None
    project_id: str | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None = None
    status: str
    priority: str
    due_date: datetime | None = None
    start_date: datetime | None = None
    assignee_id: str | None = None
    project_id: str | None = None
    group_id: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
