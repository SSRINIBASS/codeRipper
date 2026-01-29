"""
Repos API - Repository management endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware import validate_api_key
from app.models import APIKey
from app.schemas import (
    EntryPoint,
    RepoEntrypointsResponse,
    RepoIngestRequest,
    RepoIngestResponse,
    RepoStatusResponse,
    RepoStructureResponse,
    RepoSummaryResponse,
)
from app.services import check_api_readiness, get_repository
from app.services.ingestion import (
    build_file_tree,
    detect_entry_points,
    ingest_repository,
)

settings = get_settings()
router = APIRouter(prefix="/repos", tags=["Repositories"])


@router.post("/ingest", response_model=RepoIngestResponse)
async def ingest_repo(
    request: RepoIngestRequest,
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> RepoIngestResponse:
    """
    Start ingestion of a GitHub repository.
    
    Clones the repository, analyzes its structure, and prepares it for indexing.
    Returns a job ID that can be used to track progress.
    """
    repo, job = await ingest_repository(
        db,
        str(request.repo_url),
        force=request.force,
    )
    
    return RepoIngestResponse(
        repo_id=repo.id,
        job_id=job.id,
        status=repo.status,
        message=f"Ingestion started for {repo.owner}/{repo.name}",
    )


@router.get("/{repo_id}/status", response_model=RepoStatusResponse)
async def get_repo_status(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> RepoStatusResponse:
    """
    Get the current status of a repository.
    
    Returns lifecycle state, statistics, and error information if applicable.
    """
    repo = await get_repository(db, repo_id)
    
    return RepoStatusResponse(
        repo_id=repo.id,
        repo_url=repo.repo_url,
        name=repo.name,
        owner=repo.owner,
        status=repo.status,
        primary_language=repo.primary_language,
        commit_hash=repo.commit_hash,
        total_files=repo.total_files,
        total_size_bytes=repo.total_size_bytes,
        total_chunks=repo.total_chunks,
        error_message=repo.error_message,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


@router.get("/{repo_id}/summary", response_model=RepoSummaryResponse)
async def get_repo_summary(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> RepoSummaryResponse:
    """
    Get a high-level summary of the repository.
    
    Requires STRUCTURED state. Returns generated description, purpose, and key features.
    """
    repo = await check_api_readiness(db, repo_id, "summary")
    
    # Generate summary based on structure
    # This would use LLM in production, simplified for now
    return RepoSummaryResponse(
        repo_id=repo.id,
        name=repo.name,
        owner=repo.owner,
        description=f"A {repo.primary_language or 'multi-language'} repository",
        primary_language=repo.primary_language,
        languages=[repo.primary_language] if repo.primary_language else [],
        purpose=f"Repository {repo.owner}/{repo.name}",
        key_features=[],
    )


@router.get("/{repo_id}/structure", response_model=RepoStructureResponse)
async def get_repo_structure(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> RepoStructureResponse:
    """
    Get the file structure of the repository.
    
    Requires STRUCTURED state. Returns a tree of files and directories.
    """
    repo = await check_api_readiness(db, repo_id, "structure")
    
    # Build file tree
    repo_path = settings.repos_path / repo_id
    tree = build_file_tree(repo_path)
    
    # Count directories
    def count_dirs(nodes: list) -> int:
        count = 0
        for node in nodes:
            if node.type == "directory":
                count += 1
                count += count_dirs(node.children)
        return count
    
    return RepoStructureResponse(
        repo_id=repo.id,
        name=repo.name,
        total_files=repo.total_files or 0,
        total_directories=count_dirs(tree),
        tree=tree,
    )


@router.get("/{repo_id}/entrypoints", response_model=RepoEntrypointsResponse)
async def get_repo_entrypoints(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> RepoEntrypointsResponse:
    """
    Get detected entry points in the repository.
    
    Requires STRUCTURED state. Identifies main files, CLI entry points, and application starters.
    """
    repo = await check_api_readiness(db, repo_id, "entrypoints")
    
    # Detect entry points
    repo_path = settings.repos_path / repo_id
    entrypoints = detect_entry_points(repo_path, repo.primary_language)
    
    return RepoEntrypointsResponse(
        repo_id=repo.id,
        entrypoints=entrypoints,
        primary_entrypoint=entrypoints[0] if entrypoints else None,
    )
