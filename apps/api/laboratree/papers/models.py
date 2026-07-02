"""Paper ORM models. Embeddings use pgvector (text-embedding-3-small -> 1536 dims)."""

from __future__ import annotations

import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.orm import Base, OrgScopedMixin, PkMixin, TimestampMixin

EMBEDDING_DIM = 1536


class PaperStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    CARDED = "carded"
    FAILED = "failed"


class ExperimentStatus(str, enum.Enum):
    CREATED = "created"
    AWAITING_DATA = "awaiting_data"   # HITL: some datasets need manual upload
    READY = "ready"                   # all data present; walkthrough runnable
    FAILED = "failed"


class Paper(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "papers"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), default="")
    filename: Mapped[str] = mapped_column(String(300), default="")
    storage_key: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus, name="paper_status", native_enum=False,
             values_callable=lambda e: [m.value for m in e]),
        default=PaperStatus.UPLOADED,
        nullable=False,
    )
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    card: Mapped[dict] = mapped_column(JSONB, default=dict)          # the Paper Card
    simplifications: Mapped[dict] = mapped_column(JSONB, default=dict)  # cached {field: [levels]}

    chunks: Mapped[list[PaperChunk]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class PaperChunk(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "paper_chunks"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    paper: Mapped[Paper] = relationship(back_populates="chunks")


class Experiment(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    """A reproduce-and-explore run of a paper: fetched data + pipeline walkthrough."""

    __tablename__ = "experiments"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name="experiment_status", native_enum=False,
             values_callable=lambda e: [m.value for m in e]),
        default=ExperimentStatus.CREATED,
        nullable=False,
    )
    walkthrough: Mapped[list] = mapped_column(JSONB, default=list)   # ordered node graph
    fetch_report: Mapped[dict] = mapped_column(JSONB, default=dict)  # {fetched:[...], unresolved:[...]}
