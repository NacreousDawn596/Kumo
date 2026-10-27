"""Group routes: creation, membership, roles, invitations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    Conversation,
    ConversationMember,
    Group,
    GroupInvitation,
    GroupMember,
    User,
    utcnow,
)
from app.security.authz import group_role, is_group_member
from app.security.deps import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])

ROLE_RANK = {"viewer": 0, "member": 1, "moderator": 2, "admin": 3, "owner": 4}


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class GroupPatch(BaseModel):
    name: str | None = None
    description: str | None = None


def _out(db: Session, group: Group, user: User) -> dict:
    members = db.execute(select(GroupMember).where(GroupMember.group_id == group.id)).scalars().all()
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "owner_id": group.owner_id,
        "archived": group.archived_at is not None,
        "my_role": group_role(db, user.id, group.id),
        "members": [{"user_id": m.user_id, "role": m.role} for m in members],
        "created_at": group.created_at,
    }


def _require_role(db: Session, user: User, group_id: str, minimum: str) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    role = group_role(db, user.id, group_id)
    if role is None or ROLE_RANK.get(role, -1) < ROLE_RANK[minimum]:
        raise HTTPException(status_code=403, detail="Insufficient group role")
    return group


def _add_member(db: Session, group: Group, user_id: str, role: str = "member") -> None:
    """Add a user to a group AND its group conversation (kept in sync)."""
    existing = db.execute(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user_id)
    ).scalar_one_or_none()
    if existing is None:
        db.add(GroupMember(group_id=group.id, user_id=user_id, role=role))
    conv = db.execute(
        select(Conversation).where(Conversation.group_id == group.id)
    ).scalar_one_or_none()
    if conv is not None:
        cm = db.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conv.id,
                ConversationMember.user_id == user_id,
            )
        ).scalar_one_or_none()
        if cm is None:
            db.add(ConversationMember(conversation_id=conv.id, user_id=user_id))


@router.get("")
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = [m.group_id for m in db.execute(select(GroupMember).where(GroupMember.user_id == user.id)).scalars()]
    groups = db.execute(select(Group).where(Group.id.in_(ids))).scalars().all() if ids else []
    return [_out(db, g, user) for g in groups]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(body: GroupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = Group(name=body.name, description=body.description, owner_id=user.id)
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=user.id, role="owner"))
    # Group conversation.
    conv = Conversation(kind="group", group_id=group.id, title=body.name)
    db.add(conv)
    db.flush()
    db.add(ConversationMember(conversation_id=conv.id, user_id=user.id))
    db.commit()
    db.refresh(group)
    return _out(db, group, user)


@router.get("/{group_id}")
def get_group(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None or not is_group_member(db, user.id, group_id):
        raise HTTPException(status_code=404, detail="Group not found")
    return _out(db, group, user)


@router.patch("/{group_id}")
def update_group(group_id: str, body: GroupPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = _require_role(db, user, group_id, "admin")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(group, key, value)
    db.commit()
    db.refresh(group)
    return _out(db, group, user)


class InviteIn(BaseModel):
    email: str | None = None
    invitee_id: str | None = None
    role: str = "member"


class AddMemberIn(BaseModel):
    user_id: str
    role: str = "member"


@router.post("/{group_id}/invitations", status_code=status.HTTP_201_CREATED)
def invite(group_id: str, body: InviteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(db, user, group_id, "admin")
    invite = GroupInvitation(group_id=group_id, email=body.email, invitee_id=body.invitee_id, inviter_id=user.id, role=body.role)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return {"id": invite.id, "status": invite.status}


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(group_id: str, body: AddMemberIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = _require_role(db, user, group_id, "admin")
    target = db.get(User, body.user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role not in ROLE_RANK:
        raise HTTPException(status_code=400, detail="Invalid role")
    _add_member(db, group, body.user_id, body.role)
    db.commit()
    return _out(db, group, user)


@router.post("/{group_id}/join")
def join_group(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if is_group_member(db, user.id, group_id):
        return _out(db, group, user)
    _add_member(db, group, user.id, "member")
    db.commit()
    return _out(db, group, user)


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite = db.get(GroupInvitation, invitation_id)
    if invite is None or invite.status != "pending":
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invite.invitee_id is not None and invite.invitee_id != user.id:
        raise HTTPException(status_code=403, detail="Invitation is not for you")
    group = db.get(Group, invite.group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    _add_member(db, group, user.id, invite.role)
    invite.status = "accepted"
    db.commit()
    return _out(db, group, user)


@router.get("/{group_id}/invitations")
def list_invitations(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(db, user, group_id, "admin")
    invites = db.execute(select(GroupInvitation).where(GroupInvitation.group_id == group_id)).scalars().all()
    return [{"id": i.id, "email": i.email, "invitee_id": i.invitee_id, "role": i.role, "status": i.status} for i in invites]


class RoleIn(BaseModel):
    user_id: str
    role: str


@router.put("/{group_id}/members/{user_id}/role")
def set_role(group_id: str, user_id: str, body: RoleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_role(db, user, group_id, "admin")
    member = db.execute(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if body.role not in ROLE_RANK:
        raise HTTPException(status_code=400, detail="Invalid role")
    if member.role == "owner" and user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot change the owner's role")
    member.role = body.role
    db.commit()
    return {"ok": True}


@router.post("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_group(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.execute(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user.id)).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Not a member")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Owner must transfer ownership before leaving")
    db.delete(member)
    db.commit()
    return None


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None or group.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Group not found")
    group.archived_at = utcnow()
    db.commit()
    return None
