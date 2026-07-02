"""Auth & tenancy dependencies: resolve the current user, active org, and role.

The active organization is taken from the ``X-Org-Id`` header if present (and membership is
verified), otherwise from the ``org`` claim in the JWT. Every tenant-scoped query must filter
by ``principal.org_id``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..tenancy.models import Membership, Role, User
from .db.postgres import get_session
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class Principal:
    user: User
    org_id: uuid.UUID
    role: Role


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise _unauthorized("missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:
        raise _unauthorized("invalid token") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("user not found or inactive")
    return user


async def get_principal(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    x_org_id: Annotated[str | None, Header(alias="X-Org-Id")] = None,
) -> Principal:
    user = await get_current_user(session, creds)
    payload = decode_access_token(creds.credentials)  # already validated above

    raw_org = x_org_id or payload.get("org")
    if not raw_org:
        raise HTTPException(status_code=400, detail="no active organization (set X-Org-Id)")
    try:
        org_id = uuid.UUID(str(raw_org))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid org id") from exc

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id, Membership.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="not a member of this organization")

    return Principal(user=user, org_id=org_id, role=membership.role)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_role(minimum: Role):
    """Dependency factory enforcing a minimum role on the active org."""

    async def _dep(principal: PrincipalDep) -> Principal:
        if principal.role.rank < minimum.rank:
            raise HTTPException(
                status_code=403,
                detail=f"requires role >= {minimum.value}, have {principal.role.value}",
            )
        return principal

    return _dep
