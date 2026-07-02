"""Organizations: list memberships, create an org, and switch the active org (token)."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
