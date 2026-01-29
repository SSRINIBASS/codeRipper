"""
TutorSession Model - Session and message tracking for tutor interactions.

Implements memory scoping as specified: repo-scoped and session-scoped.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.repository import Repository


class TutorSession(Base):
    """Tutor session for a repository."""

    __tablename__ = "tutor_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    repo_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Context (repo-scoped, static for session)
    repo_context_summary: Mapped[str | None] = mapped_column(Text)

    # Rolling summary (≤500 tokens as per spec)
    rolling_conversation_summary: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="tutor_sessions"
    )
    messages: Mapped[list["TutorMessage"]] = relationship(
        "TutorMessage", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TutorSession {self.id[:8]} for repo {self.repo_id[:8]}>"


class TutorMessage(Base):
    """Individual message in a tutor session."""

    __tablename__ = "tutor_messages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # References cited in assistant response (JSON array)
    references: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped["TutorSession"] = relationship(
        "TutorSession", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<TutorMessage {self.role} in {self.session_id[:8]}>"
