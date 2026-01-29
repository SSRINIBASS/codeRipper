"""
Intelligence API - Indexing, search, and documentation endpoints.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware import validate_api_key
from app.models import APIKey, JobType
from app.schemas import (
    DocsArchitectureResponse,
    DocsGenerateRequest,
    DocsGenerateResponse,
    DocsReadmeResponse,
    IndexRequest,
    IndexResponse,
    SearchRequest,
    SearchResponse,
)
from app.services import check_api_readiness, create_job
from app.services.documentation import get_architecture, get_readme, start_docs_generation
from app.services.indexing import start_indexing
from app.services.search import search_code

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


@router.post("/{repo_id}/index", response_model=IndexResponse)
async def index_repository(
    repo_id: Annotated[str, Path(description="Repository ID")],
    request: IndexRequest = IndexRequest(),
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> IndexResponse:
    """
    Start semantic indexing for a repository.
    
    Chunks code, generates embeddings, and builds a vector index.
    Requires STRUCTURED state or higher.
    """
    job = await start_indexing(db, repo_id, force=request.force)
    
    return IndexResponse(
        repo_id=repo_id,
        job_id=job.id,
        message="Indexing started",
    )


@router.get("/{repo_id}/search", response_model=SearchResponse)
async def search_repository(
    repo_id: Annotated[str, Path(description="Repository ID")],
    q: Annotated[str, Query(min_length=3, max_length=500, description="Search query")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    min_score: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
    file_filter: Annotated[str | None, Query(description="Glob pattern")] = None,
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> SearchResponse:
    """
    Perform semantic search over the indexed codebase.
    
    Requires INDEXED state. Returns ranked results with code snippets.
    """
    results, total = await search_code(
        db,
        repo_id,
        q,
        limit=limit,
        offset=offset,
        min_score=min_score,
        file_filter=file_filter,
    )
    
    return SearchResponse(
        repo_id=repo_id,
        query=q,
        results=results,
        total=total,
        has_more=offset + len(results) < total,
    )


@router.post("/{repo_id}/docs", response_model=DocsGenerateResponse)
async def generate_docs(
    repo_id: Annotated[str, Path(description="Repository ID")],
    request: DocsGenerateRequest = DocsGenerateRequest(),
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> DocsGenerateResponse:
    """
    Start documentation generation for a repository.
    
    Generates README and architecture documentation using LLM.
    Requires INDEXED state.
    """
    job = await start_docs_generation(db, repo_id, force=request.force)
    
    return DocsGenerateResponse(
        repo_id=repo_id,
        job_id=job.id,
        message="Documentation generation started",
    )


@router.get("/{repo_id}/docs/readme", response_model=DocsReadmeResponse)
async def get_docs_readme(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> DocsReadmeResponse:
    """
    Get the generated README documentation.
    
    Requires DOCS_GENERATED state.
    """
    content = await get_readme(db, repo_id)
    
    return DocsReadmeResponse(
        repo_id=repo_id,
        content=content,
        generated_at=datetime.utcnow().isoformat(),
    )


@router.get("/{repo_id}/docs/architecture", response_model=DocsArchitectureResponse)
async def get_docs_architecture(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> DocsArchitectureResponse:
    """
    Get the generated architecture documentation.
    
    Requires DOCS_GENERATED state.
    """
    content = await get_architecture(db, repo_id)
    
    return DocsArchitectureResponse(
        repo_id=repo_id,
        content=content,
        components=[],  # TODO: Parse from content
        generated_at=datetime.utcnow().isoformat(),
    )
