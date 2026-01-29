"""
CodeChunk Model - Indexed code segments for semantic search.

Stores code chunks with metadata for vector search and retrieval.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.repository import Repository


class CodeChunk(Base):
    """Code chunk entity for semantic indexing."""

    __tablename__ = "code_chunks"

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

    # File location
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    # Code identification
    symbol_type: Mapped[str | None] = mapped_column(
        String(64)
    )  # function, class, method, module
    symbol_name: Mapped[str | None] = mapped_column(String(256))
    language: Mapped[str | None] = mapped_column(String(64))

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)

    # Vector reference (index in FAISS)
    embedding_index: Mapped[int | None] = mapped_column(Integer, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="code_chunks"
    )

    @property
    def location(self) -> str:
        """Get formatted location string."""
        if self.start_line == self.end_line:
            return f"{self.file_path}:{self.start_line}"
        return f"{self.file_path}:{self.start_line}-{self.end_line}"

    @property
    def symbol(self) -> str | None:
        """Get formatted symbol string."""
        if self.symbol_type and self.symbol_name:
            return f"{self.symbol_type}:{self.symbol_name}"
        return self.symbol_name

    def __repr__(self) -> str:
        return f"<CodeChunk {self.location}>"
