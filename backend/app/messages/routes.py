"""Conversation and message routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    Conversation,
    ConversationMember,
    Message,
    MessageReaction,
    MessageRead,
    User,
    utcnow,
)
from app.security.authz import is_group_member
from app.security.deps import get_current_user
from app.messages.schemas import ConversationOut, MessageIn, MessageOut, MessagePatch

router = APIRouter(tags=["messages"])


def _member(db: Session, conversation_id: str, user_id: str) -> ConversationMember | None:
    return db.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    ).scalar_one_or_none()


def _require_member(db: Session, conversation_id: str, user: User) -> None:
    if _member(db, conversation_id, user.id) is None:
        raise HTTPException(status_code=403, detail="Not a member of this conversation")


def _serialize_message(msg: Message, reactions: list[dict] | None = None) -> MessageOut:
    return MessageOut(
        id=msg.id, conversation_id=msg.conversation_id, sender_id=msg.sender_id,
        body=msg.body, created_at=msg.created_at, edited_at=msg.edited_at,
        deleted_at=msg.deleted_at, reply_to_id=msg.reply_to_id,
        link_resource_type=msg.link_resource_type, link_resource_id=msg.link_resource_id,
        reactions=reactions if reactions is not None else [],
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv_ids = [
        m.conversation_id
        for m in db.execute(select(ConversationMember).where(ConversationMember.user_id == user.id)).scalars()
    ]
    out = []
    for cid in conv_ids:
        conv = db.get(Conversation, cid)
        if conv is None:
            continue
        last = db.execute(
            select(Message).where(Message.conversation_id == cid, Message.deleted_at.is_(None)).order_by(Message.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        my_member = _member(db, cid, user.id)
        unread = 0
        if last:
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            unread = db.execute(
                select(func.count()).select_from(Message).where(
                    Message.conversation_id == cid,
                    Message.sender_id != user.id,
                    Message.created_at > (my_member.last_read_at or epoch),
                )
            ).scalar_one()
        other_ids = [
            m.user_id
            for m in db.execute(select(ConversationMember).where(ConversationMember.conversation_id == cid, ConversationMember.user_id != user.id)).scalars()
        ]
        out.append(ConversationOut(
            id=conv.id, kind=conv.kind, title=conv.title, group_id=conv.group_id,
            other_user_ids=other_ids,
            last_message=_serialize_message(last) if last else None,
            unread_count=unread,
            updated_at=last.created_at if last else conv.updated_at,
        ))
    out.sort(key=lambda c: c.updated_at or c.updated_at or utcnow(), reverse=True)
    return out


class DirectIn(BaseModel):
    other_user_id: str


@router.post("/conversations/direct", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def start_direct(body: DirectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    other = db.get(User, body.other_user_id)
    if other is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Find existing direct conversation between these two.
    existing = None
    for conv in db.execute(select(Conversation).where(Conversation.kind == "direct")).scalars():
        mids = {m.user_id for m in conv.members}
        if mids == {user.id, other.id}:
            existing = conv
            break
    if existing is None:
        conv = Conversation(kind="direct")
        db.add(conv)
        db.flush()
        db.add_all([
            ConversationMember(conversation_id=conv.id, user_id=user.id),
            ConversationMember(conversation_id=conv.id, user_id=other.id),
        ])
        db.commit()
        db.refresh(conv)
        existing = conv
    return ConversationOut(id=existing.id, kind="direct", other_user_ids=[other.id])


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: str,
    before: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_member(db, conversation_id, user)
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if before:
        anchor = db.get(Message, before)
        if anchor:
            stmt = stmt.where(Message.created_at < anchor.created_at)
    msgs = db.execute(stmt.order_by(Message.created_at.desc()).limit(limit)).scalars().all()
    out = []
    for m in reversed(msgs):
        reactions = [
            {"emoji": r.emoji, "user_id": r.user_id}
            for r in db.execute(select(MessageReaction).where(MessageReaction.message_id == m.id)).scalars()
        ]
        out.append(_serialize_message(m, reactions))
    return out


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(conversation_id: str, body: MessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_member(db, conversation_id, user)
    msg = Message(
        conversation_id=conversation_id,
        sender_id=user.id,
        body=body.body,
        reply_to_id=body.reply_to_id,
        link_resource_type=body.link_resource_type,
        link_resource_id=body.link_resource_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _serialize_message(msg)


@router.patch("/messages/{message_id}", response_model=MessageOut)
def edit_message(message_id: str, body: MessagePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = db.get(Message, message_id)
    if msg is None or msg.sender_id != user.id or msg.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.body = body.body
    msg.edited_at = utcnow()
    db.commit()
    db.refresh(msg)
    return _serialize_message(msg)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = db.get(Message, message_id)
    if msg is None or msg.sender_id != user.id:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.deleted_at = utcnow()
    msg.body = ""
    db.commit()
    return None


class ReactIn(BaseModel):
    emoji: str


@router.post("/messages/{message_id}/reactions", status_code=status.HTTP_201_CREATED)
def react(message_id: str, body: ReactIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = db.get(Message, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    _require_member(db, msg.conversation_id, user)
    existing = db.execute(
        select(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user.id,
            MessageReaction.emoji == body.emoji,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(MessageReaction(message_id=message_id, user_id=user.id, emoji=body.emoji))
        db.commit()
    return {"ok": True}


@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = _member(db, conversation_id, user.id)
    if member is None:
        raise HTTPException(status_code=403, detail="Not a member")
    member.last_read_at = utcnow()
    db.commit()
    return None
