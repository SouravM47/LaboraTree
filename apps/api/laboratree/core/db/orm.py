"""Shared ORM building blocks: the declarative Base and common mixins.

Every domain table gets a UUID primary key and created/updated timestamps. Tenant-owned
tables additionally carry an indexed ``org_id`` for row-level isolation (app-level scoping
enforced by the tenant-scoped session dependency).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .postgres import Base

__all__ = ["Base", "PkMixin", "TimestampMixin", "OrgScopedMixin"]


class PkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OrgScopedMixin:
    """Adds an indexed org_id FK for tenant isolation."""

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
