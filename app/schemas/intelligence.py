"""
Intelligence Schemas - Pydantic models for search and indexing API.
"""

from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    """Request to start indexing a repository."""

    force: bool = Field(
        default=False,
        description="Force re-indexing even if already indexed",
    )


class IndexResponse(BaseModel):
    """Response after starting indexing job."""

    repo_id: str
    job_id: str
    message: str


class SearchRequest(BaseModel):
    """Semantic search request."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language search query",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Result offset for pagination",
    )
    file_filter: str | None = Field(
        None,
        description="Glob pattern to filter files (e.g., '*.py')",
    )
    min_score: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold",
    )


class SearchResult(BaseModel):
    """Single search result."""

    file_path: str
    symbol: str | None = Field(None, description="Symbol name if available")
    symbol_type: str | None = Field(None, description="Type of symbol")
    start_line: int
    end_line: int
    content: str = Field(..., description="Matching code content")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    language: str | None = None


class SearchResponse(BaseModel):
    """Semantic search response."""

    repo_id: str
    query: str
    results: list[SearchResult]
    total: int
    has_more: bool


class DocsGenerateRequest(BaseModel):
    """Request to generate documentation."""

    force: bool = Field(
        default=False,
        description="Force regeneration even if docs exist",
    )
    sections: list[str] = Field(
        default=["readme", "architecture"],
        description="Sections to generate",
    )


class DocsGenerateResponse(BaseModel):
    """Response after starting documentation generation."""

    repo_id: str
    job_id: str
    message: str


class DocsReadmeResponse(BaseModel):
    """Generated README documentation."""

    repo_id: str
    content: str = Field(..., description="Generated README in Markdown")
    generated_at: str


class DocsArchitectureResponse(BaseModel):
    """Generated architecture documentation."""

    repo_id: str
    content: str = Field(..., description="Architecture explanation in Markdown")
    components: list[dict] = Field(
        default_factory=list,
        description="List of identified components",
    )
    generated_at: str
