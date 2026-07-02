"""Seed a demo organization with one user per role.

Run:  cd apps/api && uv run python -m laboratree.scripts.seed_demo
(honours POSTGRES_PORT etc. from the environment / .env)

Demo credentials (password is the same for all): demo12345
  owner@demo.lab · admin@demo.lab · analyst@demo.lab · viewer@demo.lab
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from ..core.db.postgres import dispose, sessionmaker
from ..core.security import hash_password
from ..tenancy.models import Membership, Organization, Role, User

PASSWORD = "demo12345"
DEMO_USERS = [
    ("owner@demo.lab", Role.OWNER, "Demo Owner"),
    ("admin@demo.lab", Role.ADMIN, "Demo Admin"),
    ("analyst@demo.lab", Role.ANALYST, "Demo Analyst"),
    ("viewer@demo.lab", Role.VIEWER, "Demo Viewer"),
]


async def main() -> None:
    async with sessionmaker()() as s:
        org = (
            await s.execute(select(Organization).where(Organization.slug == "demo-lab"))
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name="Demo Lab", slug="demo-lab")
            s.add(org)
            await s.flush()

        for email, role, name in DEMO_USERS:
            user = (
                await s.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is None:
                user = User(email=email, hashed_password=hash_password(PASSWORD), full_name=name)
                s.add(user)
                await s.flush()

            membership = (
                await s.execute(
                    select(Membership).where(
                        Membership.user_id == user.id, Membership.org_id == org.id
                    )
                )
            ).scalar_one_or_none()
            if membership is None:
                s.add(Membership(user_id=user.id, org_id=org.id, role=role))
            else:
                membership.role = role

        await s.commit()

    await dispose()
    print("Seeded 'Demo Lab' with 4 users. Password for all:", PASSWORD)
    for email, role, _ in DEMO_USERS:
        print(f"  {email:22s} role={role.value}")


if __name__ == "__main__":
    asyncio.run(main())
