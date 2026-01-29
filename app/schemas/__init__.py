"""Schemas package - Pydantic API models."""

from app.schemas.intelligence import (
    DocsArchitectureResponse,
    DocsGenerateRequest,
    DocsGenerateResponse,
    DocsReadmeResponse,
    IndexRequest,
    IndexResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.schemas.job import JobListResponse, JobResponse
from app.schemas.repository import (
    EntryPoint,
    FileNode,
    RepoEntrypointsResponse,
    RepoIngestRequest,
    RepoIngestResponse,
    RepoStatusResponse,
    RepoStructureResponse,
    RepoSummaryResponse,
)
from app.schemas.tutor import (
    AskRequest,
    AskResponse,
    CodeReference,
    RoadmapResponse,
    RoadmapStep,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionInfoResponse,
)

__all__ = [
    # Repository
    "RepoIngestRequest",
    "RepoIngestResponse",
    "RepoStatusResponse",
    "RepoSummaryResponse",
    "RepoStructureResponse",
    "RepoEntrypointsResponse",
    "FileNode",
    "EntryPoint",
    # Job
    "JobResponse",
    "JobListResponse",
    # Intelligence
    "IndexRequest",
    "IndexResponse",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "DocsGenerateRequest",
    "DocsGenerateResponse",
    "DocsReadmeResponse",
    "DocsArchitectureResponse",
    # Tutor
    "SessionCreateRequest",
    "SessionCreateResponse",
    "SessionInfoResponse",
    "AskRequest",
    "AskResponse",
    "CodeReference",
    "RoadmapResponse",
    "RoadmapStep",
]
