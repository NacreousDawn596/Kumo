"""Knowledge models: pages, blocks, links, backlinks, databases."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class Page(IdMixin, TimestampMixin, Base):
    __tablename__ = "pages"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), index=True, nullable=True
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)  # canonical markdown cache
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # optimistic concurrency

    children: Mapped[list["Page"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", foreign_keys="Page.parent_id"
    )
    parent: Mapped["Page | None"] = relationship(
        back_populates="children", remote_side="Page.id"
    )
    blocks: Mapped[list["PageBlock"]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="PageBlock.position"
    )
    permissions: Mapped[list["PagePermission"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class PageBlock(IdMixin, Base):
    __tablename__ = "page_blocks"

    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    parent_block_id: Mapped[str | None] = mapped_column(
        ForeignKey("page_blocks.id", ondelete="CASCADE"), nullable=True
    )
    block_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    page: Mapped["Page"] = relationship(back_populates="blocks")


class PageRevision(IdMixin, TimestampMixin, Base):
    __tablename__ = "page_revisions"

    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class PagePermission(IdMixin, TimestampMixin, Base):
    __tablename__ = "page_permissions"
    __table_args__ = (UniqueConstraint("page_id", "subject_type", "subject_id", name="uq_page_perm"),)

    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user|group|session
    subject_id: Mapped[str] = mapped_column(String(32), nullable=False)
    permission: Mapped[str] = mapped_column(String(16), default="view", nullable=False)
    # view|comment|edit|manage

    page: Mapped["Page"] = relationship(back_populates="permissions")


class PageLink(IdMixin, TimestampMixin, Base):
    __tablename__ = "page_links"

    source_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(32), default="page", nullable=False)
    target_resource_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # excerpt/location


class PageTag(Base):
    __tablename__ = "page_tags"
    __table_args__ = (UniqueConstraint("page_id", "tag_id", name="uq_page_tag"),)

    page_id: Mapped[str] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Database(IdMixin, TimestampMixin, Base):
    __tablename__ = "databases"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[str | None] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )


class DatabaseProperty(IdMixin, Base):
    __tablename__ = "database_properties"

    database_id: Mapped[str] = mapped_column(
        ForeignKey("databases.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    prop_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # title|text|number|checkbox|select|multi_select|date|date_range|person|url|file|relation|formula
    options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DatabaseView(IdMixin, Base):
    __tablename__ = "database_views"

    database_id: Mapped[str] = mapped_column(
        ForeignKey("databases.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    view_type: Mapped[str] = mapped_column(String(16), nullable=False)  # table|list|board|calendar|gallery
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DatabaseRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "database_records"

    database_id: Mapped[str] = mapped_column(
        ForeignKey("databases.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[str | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"), nullable=True
    )


class DatabaseRecordValue(Base):
    __tablename__ = "database_record_values"
    __table_args__ = (UniqueConstraint("record_id", "property_id", name="uq_record_value"),)

    record_id: Mapped[str] = mapped_column(
        ForeignKey("database_records.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[str] = mapped_column(
        ForeignKey("database_properties.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    value_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class DatabaseRelation(IdMixin, Base):
    __tablename__ = "database_relations"

    database_id: Mapped[str] = mapped_column(
        ForeignKey("databases.id", ondelete="CASCADE"), index=True
    )
    source_property_id: Mapped[str] = mapped_column(
        ForeignKey("database_properties.id", ondelete="CASCADE"), index=True
    )
    target_database_id: Mapped[str] = mapped_column(
        ForeignKey("databases.id", ondelete="CASCADE"), index=True
    )
