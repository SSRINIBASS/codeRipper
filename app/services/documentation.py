"""
Documentation Service - LLM-powered documentation generation.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.llm import generate_completion
from app.models import Job, JobType, Repository, RepoStatus
from app.services import jobs as jobs_service
from app.services import lifecycle

settings = get_settings()
logger = structlog.get_logger(__name__)

README_SYSTEM_PROMPT = """You are a technical documentation expert. Generate a clear, 
professional README for a code repository based on the provided analysis.
Focus on: purpose, installation, usage, and key features.
Use Markdown formatting. Be concise but comprehensive."""

ARCHITECTURE_SYSTEM_PROMPT = """You are a software architect. Explain the architecture
of a codebase based on the provided analysis. Focus on: main components, 
data flow, key patterns, and how modules interact.
Use Markdown formatting with headers and diagrams if helpful."""


async def start_docs_generation(
    db: AsyncSession,
    repo_id: str,
    force: bool = False,
) -> Job:
    """Start documentation generation job."""
    repo = await lifecycle.get_repository(db, repo_id)
    
    # Must be indexed first
    if not repo.has_reached_state(RepoStatus.INDEXED):
        from app.core.errors import RepoNotReadyError
        raise RepoNotReadyError(
            repo_id=repo_id,
            current_state=repo.status.value,
            required_state=RepoStatus.INDEXED.value,
        )
    
    # Check if already generated
    if repo.status.value >= RepoStatus.DOCS_GENERATED.value and not force:
        jobs = await jobs_service.get_jobs_for_repo(db, repo_id)
        for job in jobs:
            if job.type == JobType.DOCS:
                return job
    
    # Create docs job
    job = await jobs_service.create_job(db, repo_id, JobType.DOCS)
    
    await logger.ainfo(
        "docs_generation_started",
        repo_id=repo_id,
        job_id=job.id,
    )
    
    return job


async def execute_docs_generation(
    db: AsyncSession,
    repo: Repository,
    job: Job,
) -> Repository:
    """Execute documentation generation."""
    try:
        await jobs_service.start_job(db, job)
        
        # Build context for LLM
        context = f"""
Repository: {repo.owner}/{repo.name}
Primary Language: {repo.primary_language or 'Unknown'}
Total Files: {repo.total_files or 0}
Total Chunks: {repo.total_chunks or 0}
"""
        
        # Generate README
        await jobs_service.update_progress(db, job, 20)
        readme = await generate_completion(
            f"Generate a README for this repository:\n{context}",
            system_prompt=README_SYSTEM_PROMPT,
            max_tokens=2000,
        )
        repo.readme_content = readme
        
        # Generate Architecture doc
        await jobs_service.update_progress(db, job, 60)
        architecture = await generate_completion(
            f"Explain the architecture of this repository:\n{context}",
            system_prompt=ARCHITECTURE_SYSTEM_PROMPT,
            max_tokens=2000,
        )
        repo.architecture_content = architecture
        
        # Update status
        await lifecycle.transition_status(db, repo, RepoStatus.DOCS_GENERATED)
        
        await jobs_service.update_progress(db, job, 100)
        await jobs_service.complete_job(db, job)
        
        # Transition to READY
        await lifecycle.transition_status(db, repo, RepoStatus.READY)
        
        await logger.ainfo(
            "docs_generation_completed",
            repo_id=repo.id,
        )
        
        return repo
        
    except Exception as e:
        error_msg = str(e)
        await lifecycle.mark_failed(db, repo, error_msg)
        await jobs_service.fail_job(db, job, error_msg)
        raise


async def get_readme(
    db: AsyncSession,
    repo_id: str,
) -> str:
    """Get generated README for a repository."""
    repo = await lifecycle.check_api_readiness(db, repo_id, "docs_readme")
    return repo.readme_content or ""


async def get_architecture(
    db: AsyncSession,
    repo_id: str,
) -> str:
    """Get generated architecture doc for a repository."""
    repo = await lifecycle.check_api_readiness(db, repo_id, "docs_architecture")
    return repo.architecture_content or ""
