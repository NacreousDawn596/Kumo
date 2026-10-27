"""Collaboration models: study sessions, whiteboards, annotations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, utcnow


class StudySession(IdMixin, TimestampMixin, Base):
    __tablename__ = "study_sessions"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="scheduled", nullable=False)
    # scheduled|active|ended

    members: Mapped[list["StudySessionMember"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class StudySessionMember(Base):
    __tablename__ = "study_session_members"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["StudySession"] = relationship(back_populates="members")


class StudySessionResource(Base):
    __tablename__ = "study_session_resources"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    resource_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    added_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Whiteboard(IdMixin, TimestampMixin, Base):
    __tablename__ = "whiteboards"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=True
    )
    template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # JSON snapshot of elements for fast load
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class WhiteboardOperation(Base):
    __tablename__ = "whiteboard_operations"

    # Server-assigned monotonic sequence (SQLite AUTOINCREMENT). Clients do not
    # supply this; it guarantees a conflict-free total order for concurrent ops.
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    whiteboard_id: Mapped[str] = mapped_column(
        ForeignKey("whiteboards.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    op_type: Mapped[str] = mapped_column(String(32), nullable=False)  # add|update|remove|...
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentAnnotation(IdMixin, TimestampMixin, Base):
    __tablename__ = "document_annotations"

    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tool: Mapped[str] = mapped_column(String(32), nullable=False)  # pen|highlight|rect|text|sticky|...
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stroke_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_json: Mapped[str] = mapped_column(Text, nullable=False)  # normalized coordinates
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="SET NULL"), nullable=True
    )
