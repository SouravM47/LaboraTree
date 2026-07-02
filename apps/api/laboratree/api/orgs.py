"""Organizations: list memberships, create an org, and switch the active org (token)."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from ..core.deps import SessionDep, get_current_user
from ..core.security import create_access_token
from ..tenancy.models import Membership, Organization, Role, User

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: Role


class OrgCreateIn(BaseModel):
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org_id: uuid.UUID


@router.get("", response_model=list[OrgOut])
async def list_orgs(
    session: SessionDep,
    user: User = Depends(get_current_user),
) -> list[OrgOut]:
    rows = (
        await session.execute(
            select(Organization, Membership.role)
            .join(Membership, Membership.org_id == Organization.id)
            .where(Membership.user_id == user.id)
        )
    ).all()
    return [OrgOut(id=o.id, name=o.name, slug=o.slug, role=role) for o, role in rows]


@router.post("", response_model=OrgOut, status_code=201)
async def create_org(
    body: OrgCreateIn,
    session: SessionDep,
    user: User = Depends(get_current_user),
) -> OrgOut:
    org = Organization(name=body.name, slug=_slugify(body.name))
    session.add(org)
    await session.flush()
    session.add(Membership(user_id=user.id, org_id=org.id, role=Role.OWNER))
    await session.commit()
    return OrgOut(id=org.id, name=org.name, slug=org.slug, role=Role.OWNER)


@router.post("/{org_id}/token", response_model=TokenOut)
async def switch_org(
    org_id: uuid.UUID,
    session: SessionDep,
    user: User = Depends(get_current_user),
) -> TokenOut:
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id, Membership.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="not a member of this organization")
    token = create_access_token(str(user.id), org=str(org_id))
    return TokenOut(access_token=token, org_id=org_id)


# --------------------------- member management (RBAC) ---------------------------

class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: Role


class AddMemberIn(BaseModel):
    email: EmailStr
    role: Role = Role.ANALYST


class SetRoleIn(BaseModel):
    role: Role


async def _require_membership(session, user: User, org_id: uuid.UUID, minimum: Role) -> Membership:
    m = (
        await session.execute(
            select(Membership).where(Membership.user_id == user.id, Membership.org_id == org_id)
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="organization not found")
    if m.role.rank < minimum.rank:
        raise HTTPException(status_code=403, detail=f"requires role >= {minimum.value}")
    return m


@router.get("/{org_id}/members", response_model=list[MemberOut])
async def list_members(
    org_id: uuid.UUID, session: SessionDep, user: User = Depends(get_current_user)
) -> list[MemberOut]:
    await _require_membership(session, user, org_id, Role.VIEWER)
    rows = (
        await session.execute(
            select(User, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.org_id == org_id)
        )
    ).all()
    return [MemberOut(user_id=u.id, email=u.email, full_name=u.full_name, role=r) for u, r in rows]


@router.post("/{org_id}/members", response_model=MemberOut, status_code=201)
async def add_member(
    org_id: uuid.UUID,
    body: AddMemberIn,
    session: SessionDep,
    user: User = Depends(get_current_user),
) -> MemberOut:
    caller = await _require_membership(session, user, org_id, Role.ADMIN)
    if body.role == Role.OWNER and caller.role != Role.OWNER:
        raise HTTPException(status_code=403, detail="only an owner can grant the owner role")

    target = (
        await session.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="user must register before being added")

    existing = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == target.id, Membership.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="user is already a member")

    session.add(Membership(user_id=target.id, org_id=org_id, role=body.role))
    await session.commit()
    return MemberOut(user_id=target.id, email=target.email, full_name=target.full_name, role=body.role)


@router.patch("/{org_id}/members/{user_id}", response_model=MemberOut)
async def set_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: SetRoleIn,
    session: SessionDep,
    user: User = Depends(get_current_user),
) -> MemberOut:
    caller = await _require_membership(session, user, org_id, Role.ADMIN)
    if body.role == Role.OWNER and caller.role != Role.OWNER:
        raise HTTPException(status_code=403, detail="only an owner can grant the owner role")

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user_id, Membership.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="member not found")

    membership.role = body.role
    await session.commit()
    target = await session.get(User, user_id)
    return MemberOut(user_id=user_id, email=target.email, full_name=target.full_name, role=body.role)
