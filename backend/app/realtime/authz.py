"""Room authorization for the realtime layer."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ConversationMember,
    File,
    GroupMember,
    StudySessionMember,
    Whiteboard,
)


def room_members(db: Session, room: str) -> list[str]:
    """Return authorized member user ids for a room, or [] if unknown/empty."""
    try:
        kind, rid = room.split(":", 1)
    except ValueError:
        return []
    if kind == "conversation":
        return [m.user_id for m in db.execute(select(ConversationMember).where(ConversationMember.conversation_id == rid)).scalars()]
    if kind == "group":
        return [m.user_id for m in db.execute(select(GroupMember).where(GroupMember.group_id == rid)).scalars()]
    if kind == "session":
        return [m.user_id for m in db.execute(select(StudySessionMember).where(StudySessionMember.session_id == rid)).scalars()]
    if kind == "whiteboard":
        wb = db.get(Whiteboard, rid)
        if wb is None:
            return []
        members = {wb.owner_id}
        if wb.group_id:
            members.update(m.user_id for m in db.execute(select(GroupMember).where(GroupMember.group_id == wb.group_id)).scalars())
        return list(members)
    if kind == "file":
        from app.security.authz import file_permission
        file = db.get(File, rid)
        if file is None:
            return []
        from app.models import User
        members = {file.owner_id}
        if file.group_id:
            members.update(m.user_id for m in db.execute(select(GroupMember).where(GroupMember.group_id == file.group_id)).scalars())
        return list(members)
    return []


def can_join_room(db: Session, user_id: str, room: str) -> bool:
    return user_id in room_members(db, room)
