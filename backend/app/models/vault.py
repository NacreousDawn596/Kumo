"""Vault models: files, versions, shares, tags, collections, comments."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, utcnow


class File(IdMixin, TimestampMixin, Base):
    __tablename__ = "files"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_id: Mapped[str] = mapped_column(String(64), nullable=False)  # generated internal id
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)  # relative to storage root
    parent_folder: Mapped[str | None] = mapped_column(String(64), nullable=True)  # folder id
    is_folder: Mapped[bool] = mapped_column(default=False, nullable=False)
    previewable: Mapped[bool] = mapped_column(default=False, nullable=False)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=True
    )  # None => personal vault

    shares: Mapped[list["FileShare"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    versions: Mapped[list["FileVersion"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    comments: Mapped[list["FileComment"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )


class FileVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "file_versions"

    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    storage_id: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    file: Mapped["File"] = relationship(back_populates="versions")


class FileShare(IdMixin, TimestampMixin, Base):
    __tablename__ = "file_shares"
    __table_args__ = (
        UniqueConstraint("file_id", "shared_with_user_id", name="uq_file_share_user"),
    )

    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    shared_with_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    shared_with_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    study_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=True
    )
    permission: Mapped[str] = mapped_column(String(16), default="view", nullable=False)
    # view|download|comment|annotate|collaborate|manage

    file: Mapped["File"] = relationship(back_populates="shares")


class Tag(IdMixin, TimestampMixin, Base):
    __tablename__ = "tags"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)


class FileTag(Base):
    __tablename__ = "file_tags"
    __table_args__ = (UniqueConstraint("file_id", "tag_id", name="uq_file_tag"),)

    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Collection(IdMixin, TimestampMixin, Base):
    __tablename__ = "collections"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (UniqueConstraint("collection_id", "file_id", name="uq_collection_item"),)

    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FileComment(IdMixin, TimestampMixin, Base):
    __tablename__ = "file_comments"

    file_id: Mapped[str] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON annotation anchor
    reply_to_id: Mapped[str | None] = mapped_column(
        ForeignKey("file_comments.id", ondelete="SET NULL"), nullable=True
    )

    file: Mapped["File"] = relationship(back_populates="comments")
