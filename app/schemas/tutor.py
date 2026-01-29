"""
Tutor Schemas - Pydantic models for tutor Q&A API.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """Request to create a new tutor session."""

    initial_context: str | None = Field(
        None,
        max_length=1000,
        description="Optional initial context or focus area",
    )


class SessionCreateResponse(BaseModel):
    """Response after creating a tutor session."""

    session_id: str
    repo_id: str
    repo_context_summary: str = Field(
        ..., description="Summary of the repository context"
    )
    created_at: datetime


class AskRequest(BaseModel):
    """Request to ask the tutor a question."""

    session_id: str = Field(..., description="Active session ID")
    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Question about the repository",
    )


class CodeReference(BaseModel):
    """Code reference cited in an answer."""

    file: str = Field(..., description="File path")
    symbol: str | None = Field(None, description="Symbol name (class, function, etc.)")
    lines: str = Field(..., description="Line range (e.g., '42-87')")
    content: str | None = Field(None, description="Relevant code snippet")


class AskResponse(BaseModel):
    """Tutor answer to a question."""

    session_id: str
    question: str
    answer: str = Field(..., description="Explanation grounded in the codebase")
    references: list[CodeReference] = Field(
        default_factory=list,
        description="Code references supporting the answer",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the answer",
    )
    answered: bool = Field(
        ...,
        description="Whether the question could be answered from the codebase",
    )


class SessionInfoResponse(BaseModel):
    """Information about a tutor session."""

    session_id: str
    repo_id: str
    repo_context_summary: str
    rolling_conversation_summary: str | None
    message_count: int
    created_at: datetime
    last_activity_at: datetime


class RoadmapStep(BaseModel):
    """Step in a learning roadmap."""

    order: int
    title: str
    description: str
    files: list[str] = Field(default_factory=list, description="Relevant files")
    estimated_time: str | None = None


class RoadmapResponse(BaseModel):
    """Learning roadmap for the repository."""

    repo_id: str
    role: str = Field(..., description="Target role (contributor, maintainer, etc.)")
    steps: list[RoadmapStep]
    total_estimated_time: str | None = None
