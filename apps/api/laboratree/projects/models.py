"""Domain ORM models — the spine every Lab and agent run hangs off.

Project -> Dataset (versioned) -> Run (agent/component execution + reproducibility manifest)
       -> Artifact (blobs) -> Evidence (provenance-locked values) -> GateTask (human approvals).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.orm import Base, OrgScopedMixin, PkMixin, TimestampMixin


def _enum_col(py_enum, name):
    return Enum(py_enum, name=name, native_enum=False, values_callable=lambda e: [m.value for m in e])


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_GATE = "awaiting_gate"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class GateStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class IdeationStatus(str, enum.Enum):
    COMPLETE = "complete"
    FAILED = "failed"


class Project(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    datasets: Mapped[list[Dataset]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    runs: Mapped[list[Run]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Dataset(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="")  # sha256 for reproducibility
    storage_key: Mapped[str] = mapped_column(String(500), default="")   # BlobStore key
    n_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_cols: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="datasets")


class Run(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="component")  # component|agent|pipeline
    lab: Mapped[str] = mapped_column(String(60), default="")
    component_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        _enum_col(RunStatus, "run_status"), default=RunStatus.PENDING, nullable=False
    )
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    # reproducibility manifest: {data_hash, seeds, image_digest, code_hash, lib_versions}
    repro_manifest: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="runs")
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    gates: Mapped[list[GateTask]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Artifact(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(60), default="file")  # file|model|figure|workbook
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped[Run] = relationship(back_populates="artifacts")


class Evidence(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    """Provenance-locked record: every reported value must originate from real execution."""

    __tablename__ = "evidence"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(60), default="metric")  # metric|figure|table|claim
    value: Mapped[dict] = mapped_column(JSONB, default=dict)  # wrapped {"v": ...} for any json type
    code_hash: Mapped[str] = mapped_column(String(64), default="")
    data_version: Mapped[str] = mapped_column(String(64), default="")
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    run: Mapped[Run] = relationship(back_populates="evidence")


class GateTask(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    """A pending human-in-the-loop approval. The run pauses until this is resolved."""

    __tablename__ = "gate_tasks"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # what the human is reviewing
    status: Mapped[GateStatus] = mapped_column(
        _enum_col(GateStatus, "gate_status"), default=GateStatus.PENDING, nullable=False
    )
    response: Mapped[dict] = mapped_column(JSONB, default=dict)  # approve/edit/reject + edits
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    run: Mapped[Run] = relationship(back_populates="gates")


class IdeationSession(PkMixin, OrgScopedMixin, TimestampMixin, Base):
    """A Co-Scientist run: goal -> ranked hypotheses + meta-review."""

    __tablename__ = "ideation_sessions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IdeationStatus] = mapped_column(
        _enum_col(IdeationStatus, "ideation_status"), default=IdeationStatus.COMPLETE, nullable=False
    )
    hypotheses: Mapped[list] = mapped_column(JSONB, default=list)  # ranked list of hypothesis dicts
    meta_review: Mapped[str] = mapped_column(Text, default="")
