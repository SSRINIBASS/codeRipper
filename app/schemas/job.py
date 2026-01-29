"""
Job Schemas - Pydantic models for job tracking API.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    """Job status response."""

    job_id: str = Field(..., description="Unique job identifier")
    repo_id: str = Field(..., description="Associated repository ID")
    type: str = Field(..., description="Job type (ingest, index, docs)")
    status: str = Field(..., description="Job status (pending, running, completed, failed)")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    error_message: str | None = None
    attempt: int = Field(..., description="Current attempt number")
    max_attempts: int = Field(..., description="Maximum retry attempts")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class JobListResponse(BaseModel):
    """List of jobs for a repository."""

    repo_id: str
    jobs: list[JobResponse]
    total: int
