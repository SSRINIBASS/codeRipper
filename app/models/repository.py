"""
Repository Model - Core entity for repository lifecycle management.

Defines the Repository SQLAlchemy model and lifecycle state machine.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.code_chunk import CodeChunk
    from app.models.job import Job
    from app.models.tutor_session import TutorSession


class RepoStatus(str, enum.Enum):
    """Repository lifecycle states as specified in the design doc."""

    CREATED = "CREATED"
    CLONED = "CLONED"
    STRUCTURED = "STRUCTURED"
    INDEXED = "INDEXED"
    DOCS_GENERATED = "DOCS_GENERATED"
    READY = "READY"
    FAILED = "FAILED"


# Valid state transitions
VALID_TRANSITIONS: dict[RepoStatus, list[RepoStatus]] = {
    RepoStatus.CREATED: [RepoStatus.CLONED, RepoStatus.FAILED],
    RepoStatus.CLONED: [RepoStatus.STRUCTURED, RepoStatus.FAILED],
    RepoStatus.STRUCTURED: [RepoStatus.INDEXED, RepoStatus.FAILED],
    RepoStatus.INDEXED: [RepoStatus.DOCS_GENERATED, RepoStatus.FAILED],
    RepoStatus.DOCS_GENERATED: [RepoStatus.READY, RepoStatus.FAILED],
    RepoStatus.READY: [RepoStatus.FAILED],  # Can fail during updates
    RepoStatus.FAILED: [RepoStatus.CREATED],  # Allow retry
}

# Minimum state required for each API operation
API_STATE_REQUIREMENTS: dict[str, RepoStatus] = {
    "summary": RepoStatus.STRUCTURED,
    "structure": RepoStatus.STRUCTURED,
    "entrypoints": RepoStatus.STRUCTURED,
    "index": RepoStatus.STRUCTURED,  # Indexing can be triggered from STRUCTURED state
    "search": RepoStatus.INDEXED,
    "session": RepoStatus.INDEXED,
    "ask": RepoStatus.INDEXED,
    "docs_readme": RepoStatus.DOCS_GENERATED,
    "docs_architecture": RepoStatus.DOCS_GENERATED,
}


def state_order(status: RepoStatus) -> int:
    """Get numeric order of state for comparison."""
    order = {
        RepoStatus.CREATED: 0,
        RepoStatus.CLONED: 1,
        RepoStatus.STRUCTURED: 2,
        RepoStatus.INDEXED: 3,
        RepoStatus.DOCS_GENERATED: 4,
        RepoStatus.READY: 5,
        RepoStatus.FAILED: -1,
    }
    return order.get(status, -1)


class Repository(Base):
    """Repository entity representing an ingested GitHub repository."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    repo_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    owner: Mapped[str] = mapped_column(String(256), nullable=False)
    primary_language: Mapped[str | None] = mapped_column(String(64))
    commit_hash: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RepoStatus.CREATED.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # Statistics
    total_files: Mapped[int | None] = mapped_column(Integer)
    total_size_bytes: Mapped[int | None] = mapped_column(Integer)
    total_chunks: Mapped[int | None] = mapped_column(Integer)

    # Generated documentation (stored as JSON text)
    readme_content: Mapped[str | None] = mapped_column(Text)
    architecture_content: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="repository", cascade="all, delete-orphan"
    )
    code_chunks: Mapped[list["CodeChunk"]] = relationship(
        "CodeChunk", back_populates="repository", cascade="all, delete-orphan"
    )
    tutor_sessions: Mapped[list["TutorSession"]] = relationship(
        "TutorSession", back_populates="repository", cascade="all, delete-orphan"
    )

    def can_transition_to(self, new_status: RepoStatus) -> bool:
        """Check if transition to new status is valid."""
        current = RepoStatus(self.status) if isinstance(self.status, str) else self.status
        return new_status in VALID_TRANSITIONS.get(current, [])

    def has_reached_state(self, required_state: RepoStatus) -> bool:
        """Check if repository has reached at least the required state."""
        current = RepoStatus(self.status) if isinstance(self.status, str) else self.status
        if current == RepoStatus.FAILED:
            return False
        return state_order(current) >= state_order(required_state)

    def check_api_readiness(self, operation: str) -> tuple[bool, str | None]:
        """
        Check if repository is ready for a specific API operation.
        
        Returns:
            Tuple of (is_ready, error_message)
        """
        required = API_STATE_REQUIREMENTS.get(operation)
        if required is None:
            return True, None

        current = RepoStatus(self.status) if isinstance(self.status, str) else self.status
        if current == RepoStatus.FAILED:
            return False, f"Repository is in FAILED state: {self.error_message}"

        if not self.has_reached_state(required):
            return False, f"Repository must be in {required.value} state or later. Current: {current.value}"

        return True, None

    def __repr__(self) -> str:
        return f"<Repository {self.name} ({self.status})>"
