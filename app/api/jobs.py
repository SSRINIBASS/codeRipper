"""
Jobs API - Job tracking endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware import validate_api_key
from app.models import APIKey
from app.schemas import JobListResponse, JobResponse
from app.services import get_job, get_jobs_for_repo

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: Annotated[str, Path(description="Job ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> JobResponse:
    """
    Get the status of a job.
    
    Returns job type, status, progress, and error information if applicable.
    """
    job = await get_job(db, job_id)
    
    return JobResponse(
        job_id=job.id,
        repo_id=job.repo_id,
        type=job.type.value,
        status=job.status.value,
        progress=job.progress,
        error_message=job.error_message,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.get("/repo/{repo_id}", response_model=JobListResponse)
async def list_repo_jobs(
    repo_id: Annotated[str, Path(description="Repository ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> JobListResponse:
    """
    List all jobs for a repository.
    
    Returns jobs sorted by creation time (newest first).
    """
    jobs = await get_jobs_for_repo(db, repo_id)
    
    return JobListResponse(
        repo_id=repo_id,
        jobs=[
            JobResponse(
                job_id=job.id,
                repo_id=job.repo_id,
                type=job.type.value,
                status=job.status.value,
                progress=job.progress,
                error_message=job.error_message,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                started_at=job.started_at,
                completed_at=job.completed_at,
                created_at=job.created_at,
            )
            for job in jobs
        ],
        total=len(jobs),
    )
