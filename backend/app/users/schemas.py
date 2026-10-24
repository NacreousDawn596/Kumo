"""User serialization schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    display_name: str
    bio: str | None = None
    study_interests: str | None = None
    timezone: str
    theme: str
    language: str
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    study_interests: str | None = None
    timezone: str | None = None
    theme: str | None = None
    language: str | None = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    bio: str | None = None
