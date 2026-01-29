"""
Lifecycle Service - Repository state machine management.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RepoNotFoundError, RepoNotReadyError
from app.models import Repository, RepoStatus

logger = structlog.get_logger(__name__)


async def get_repository(
    db: AsyncSession,
    repo_id: str,
) -> Repository:
    """
    Get repository by ID.
    
    Raises:
        RepoNotFoundError: If repository doesn't exist
    """
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise RepoNotFoundError(repo_id)
    
    return repo


async def get_repository_by_url(
    db: AsyncSession,
    repo_url: str,
) -> Repository | None:
    """Get repository by URL, returns None if not found."""
    result = await db.execute(
        select(Repository).where(Repository.repo_url == repo_url)
    )
    return result.scalar_one_or_none()


async def transition_status(
    db: AsyncSession,
    repo: Repository,
    new_status: RepoStatus,
    error_message: str | None = None,
) -> Repository:
    """
    Transition repository to a new status.
    
    Args:
        db: Database session
        repo: Repository to transition
        new_status: Target status
        error_message: Optional error message for FAILED status
        
    Returns:
        Updated repository
        
    Raises:
        ValueError: If transition is invalid
    """
    if not repo.can_transition_to(new_status):
        await logger.awarning(
            "invalid_status_transition",
            repo_id=repo.id,
            current=repo.status,
            target=new_status.value,
        )
        raise ValueError(
            f"Invalid transition from {repo.status} to {new_status.value}"
        )
    
    old_status = repo.status
    repo.status = new_status.value
    
    if new_status == RepoStatus.FAILED and error_message:
        repo.error_message = error_message
    
    await db.commit()
    await db.refresh(repo)
    
    await logger.ainfo(
        "status_transitioned",
        repo_id=repo.id,
        from_status=old_status,
        to_status=new_status.value,
    )
    
    return repo


async def check_api_readiness(
    db: AsyncSession,
    repo_id: str,
    operation: str,
) -> Repository:
    """
    Check if repository is ready for an API operation.
    
    Args:
        db: Database session
        repo_id: Repository ID
        operation: API operation name
        
    Returns:
        Repository if ready
        
    Raises:
        RepoNotFoundError: If repository doesn't exist
        RepoNotReadyError: If repository isn't ready for the operation
    """
    repo = await get_repository(db, repo_id)
    
    is_ready, error = repo.check_api_readiness(operation)
    
    if not is_ready:
        from app.models.repository import API_STATE_REQUIREMENTS
        required = API_STATE_REQUIREMENTS.get(operation, RepoStatus.CREATED)
        raise RepoNotReadyError(
            repo_id=repo_id,
            current_state=repo.status,
            required_state=required.value,
        )
    
    return repo


async def mark_failed(
    db: AsyncSession,
    repo: Repository,
    error_message: str,
) -> Repository:
    """Convenience method to mark a repository as failed."""
    return await transition_status(
        db, repo, RepoStatus.FAILED, error_message
    )
