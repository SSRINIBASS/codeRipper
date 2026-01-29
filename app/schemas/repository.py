"""
Repository Schemas - Pydantic models for repository API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RepoIngestRequest(BaseModel):
    """Request to ingest a new repository."""

    repo_url: HttpUrl = Field(
        ...,
        description="Public GitHub repository URL",
        examples=["https://github.com/tiangolo/fastapi"],
    )
    force: bool = Field(
        default=False,
        description="Force re-ingestion if repository already exists",
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate that URL is a GitHub repository."""
        url_str = str(v)
        if "github.com" not in url_str:
            raise ValueError("Only GitHub repositories are supported")
        return v


class RepoIngestResponse(BaseModel):
    """Response after starting repository ingestion."""

    repo_id: str = Field(..., description="Unique repository identifier")
    job_id: str = Field(..., description="Ingestion job identifier")
    status: str = Field(..., description="Current repository status")
    message: str = Field(..., description="Status message")


class RepoStatusResponse(BaseModel):
    """Repository status information."""

    repo_id: str
    repo_url: str
    name: str
    owner: str
    status: str
    primary_language: str | None = None
    commit_hash: str | None = None
    total_files: int | None = None
    total_size_bytes: int | None = None
    total_chunks: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class RepoSummaryResponse(BaseModel):
    """Repository summary for understanding the codebase."""

    repo_id: str
    name: str
    owner: str
    description: str = Field(..., description="Generated description of the repository")
    primary_language: str | None = None
    languages: list[str] = Field(default_factory=list, description="All detected languages")
    framework: str | None = Field(None, description="Detected framework if any")
    purpose: str = Field(..., description="Inferred purpose of the repository")
    key_features: list[str] = Field(
        default_factory=list, description="Key features or capabilities"
    )


class FileNode(BaseModel):
    """File or directory in the repository structure."""

    name: str
    path: str
    type: str = Field(..., description="'file' or 'directory'")
    size: int | None = None
    language: str | None = None
    children: list["FileNode"] = Field(default_factory=list)


class RepoStructureResponse(BaseModel):
    """Repository file structure."""

    repo_id: str
    name: str
    total_files: int
    total_directories: int
    tree: list[FileNode]


class EntryPoint(BaseModel):
    """Probable entry point in the repository."""

    file_path: str
    type: str = Field(..., description="Type of entry point (main, app, cli, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reason: str = Field(..., description="Why this is considered an entry point")


class RepoEntrypointsResponse(BaseModel):
    """Identified entry points in the repository."""

    repo_id: str
    entrypoints: list[EntryPoint]
    primary_entrypoint: EntryPoint | None = Field(
        None, description="Most likely primary entry point"
    )


# Enable forward references
FileNode.model_rebuild()
