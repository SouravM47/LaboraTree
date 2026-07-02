"""Import-all module so Base.metadata sees every table (used by Alembic and app startup)."""

from .core.db.orm import Base  # noqa: F401
from .projects.models import (  # noqa: F401
    Artifact,
    Dataset,
    Evidence,
    GateStatus,
    GateTask,
    Project,
    Run,
    RunStatus,
)
from .tenancy.models import Membership, Organization, Role, User  # noqa: F401

__all__ = [
    "Base",
    "Organization",
    "User",
    "Membership",
    "Role",
    "Project",
    "Dataset",
    "Run",
    "RunStatus",
    "Artifact",
    "Evidence",
    "GateTask",
    "GateStatus",
]
