"""
Jobs Service - Async job queue management.
"""

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import JobNotFoundError
from app.models import Job, JobStatus, JobType, Repository

logger = structlog.get_logger(__name__)


async def create_job(
    db: AsyncSession,
    repo_id: str,
    job_type: JobType,
) -> Job:
    """
    Create a new job for a repository.
    
    Args:
        db: Database session
        repo_id: Repository ID
        job_type: Type of job
        
    Returns:
        Created job
    """
    job = Job(
        id=str(uuid4()),
        repo_id=repo_id,
        type=job_type.value if isinstance(job_type, JobType) else job_type,
        status=JobStatus.PENDING.value,
        progress=0,
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    await logger.ainfo(
        "job_created",
        job_id=job.id,
        repo_id=repo_id,
        type=job_type.value,
    )
    
    return job


async def get_job(db: AsyncSession, job_id: str) -> Job:
    """
    Get job by ID.
    
    Raises:
        JobNotFoundError: If job doesn't exist
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise JobNotFoundError(job_id)
    
    return job


async def start_job(db: AsyncSession, job: Job) -> Job:
    """Mark job as running."""
    job.status = JobStatus.RUNNING.value
    job.started_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(job)
    
    await logger.ainfo(
        "job_started",
        job_id=job.id,
        type=job.type,
    )
    
    return job


async def update_progress(
    db: AsyncSession,
    job: Job,
    progress: int,
) -> Job:
    """Update job progress (0-100)."""
    job.progress = min(max(progress, 0), 100)
    await db.commit()
    return job


async def complete_job(db: AsyncSession, job: Job) -> Job:
    """Mark job as completed."""
    job.status = JobStatus.COMPLETED.value
    job.progress = 100
    job.completed_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(job)
    
    await logger.ainfo(
        "job_completed",
        job_id=job.id,
        type=job.type,
        duration_seconds=(job.completed_at - job.started_at).total_seconds()
        if job.started_at
        else None,
    )
    
    return job


async def fail_job(
    db: AsyncSession,
    job: Job,
    error_message: str,
) -> Job:
    """Mark job as failed."""
    job.status = JobStatus.FAILED.value
    job.error_message = error_message
    job.completed_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(job)
    
    await logger.aerror(
        "job_failed",
        job_id=job.id,
        type=job.type,
        error=error_message,
    )
    
    return job


async def get_pending_jobs(
    db: AsyncSession,
    limit: int = 10,
) -> list[Job]:
    """Get pending jobs ordered by creation time."""
    result = await db.execute(
        select(Job)
        .where(Job.status == JobStatus.PENDING.value)
        .order_by(Job.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_jobs_for_repo(
    db: AsyncSession,
    repo_id: str,
) -> list[Job]:
    """Get all jobs for a repository."""
    result = await db.execute(
        select(Job)
        .where(Job.repo_id == repo_id)
        .order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())
