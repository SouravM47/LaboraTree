"""Authentication: register (creates a starter org), login, and current-user info."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from ..core.deps import PrincipalDep, SessionDep
from ..core.security import create_access_token, hash_password, verify_password
from ..tenancy.models import Membership, Organization, Role, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""
    org_name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org_id: uuid.UUID


class MeOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    active_org_id: uuid.UUID
    role: Role


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, session: SessionDep) -> TokenOut:
    exists = (
        await session.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    org = Organization(
        name=body.org_name or f"{(body.full_name or body.email.split('@')[0])}'s Lab",
        slug=_slugify(body.org_name or body.email.split("@")[0]),
    )
    session.add_all([user, org])
    await session.flush()
    session.add(Membership(user_id=user.id, org_id=org.id, role=Role.OWNER))
    await session.commit()

    token = create_access_token(str(user.id), org=str(org.id))
    return TokenOut(access_token=token, org_id=org.id)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, session: SessionDep) -> TokenOut:
    user = (
        await session.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="invalid credentials")

    membership = (
        await session.execute(
            select(Membership).where(Membership.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="user has no organization")

    token = create_access_token(str(user.id), org=str(membership.org_id))
    return TokenOut(access_token=token, org_id=membership.org_id)


@router.get("/me", response_model=MeOut)
async def me(principal: PrincipalDep) -> MeOut:
    return MeOut(
        id=principal.user.id,
        email=principal.user.email,
        full_name=principal.user.full_name,
        active_org_id=principal.org_id,
        role=principal.role,
    )
