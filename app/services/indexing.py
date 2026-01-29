"""
Indexing Service - Semantic indexing with embeddings.
"""

from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.chunking import chunk_repository
from app.core.llm import generate_embeddings_batch
from app.core.vector_store import VectorStore
from app.models import CodeChunk, Job, JobType, Repository, RepoStatus
from app.services import jobs as jobs_service
from app.services import lifecycle

settings = get_settings()
logger = structlog.get_logger(__name__)


async def start_indexing(
    db: AsyncSession,
    repo_id: str,
    force: bool = False,
) -> Job:
    """
    Start indexing job for a repository.
    
    Args:
        db: Database session
        repo_id: Repository ID
        force: Force re-indexing
        
    Returns:
        Created job
    """
    repo = await lifecycle.check_api_readiness(db, repo_id, "index")
    
    # Check if already indexed (use has_reached_state for proper state comparison)
    if repo.has_reached_state(RepoStatus.INDEXED) and not force:
        # Get latest job
        jobs = await jobs_service.get_jobs_for_repo(db, repo_id)
        for job in jobs:
            if job.type == JobType.INDEX.value:
                return job
    
    # Create indexing job
    job = await jobs_service.create_job(db, repo_id, JobType.INDEX)
    
    await logger.ainfo(
        "indexing_started",
        repo_id=repo_id,
        job_id=job.id,
    )
    
    return job


async def execute_indexing(
    db: AsyncSession,
    repo: Repository,
    job: Job,
) -> Repository:
    """
    Execute the indexing process.
    
    This should be called by the job worker.
    """
    try:
        # Start job
        await jobs_service.start_job(db, job)
        
        repo_path = settings.repos_path / repo.id
        
        # Chunk repository
        await jobs_service.update_progress(db, job, 10)
        chunks = list(chunk_repository(repo_path))
        
        if not chunks:
            # Even with no chunks, transition to INDEXED so lifecycle continues
            repo.total_chunks = 0
            await lifecycle.transition_status(db, repo, RepoStatus.INDEXED)
            await jobs_service.update_progress(db, job, 100)
            await jobs_service.complete_job(db, job)
            await logger.ainfo(
                "indexing_completed_no_chunks",
                repo_id=repo.id,
            )
            return repo
        
        await logger.ainfo(
            "chunks_extracted",
            repo_id=repo.id,
            count=len(chunks),
        )
        
        # Generate embeddings in batches
        await jobs_service.update_progress(db, job, 30)
        
        texts = [
            f"File: {c.file_path}\n"
            f"Symbol: {c.symbol_name or 'N/A'}\n"
            f"Type: {c.symbol_type or 'code'}\n"
            f"Lines: {c.start_line}-{c.end_line}\n\n"
            f"{c.content}"
            for c in chunks
        ]
        
        embeddings = await generate_embeddings_batch(texts)
        
        await jobs_service.update_progress(db, job, 70)
        
        # Store chunks in database and vector store
        vector_store = VectorStore(repo.id)
        vector_store.create_index()
        
        chunk_ids = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create database record
            db_chunk = CodeChunk(
                repo_id=repo.id,
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                symbol_type=chunk.symbol_type,
                symbol_name=chunk.symbol_name,
                language=chunk.language,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding_index=i,
            )
            db.add(db_chunk)
            chunk_ids.append(db_chunk.id)
        
        await db.commit()
        
        # Add to vector store
        vector_store.add_embeddings(embeddings, chunk_ids)
        vector_store.save()
        
        # Update repository
        repo.total_chunks = len(chunks)
        await lifecycle.transition_status(db, repo, RepoStatus.INDEXED)
        
        await jobs_service.update_progress(db, job, 100)
        await jobs_service.complete_job(db, job)
        
        await logger.ainfo(
            "indexing_completed",
            repo_id=repo.id,
            chunks=len(chunks),
        )
        
        return repo
        
    except Exception as e:
        error_msg = str(e)
        await lifecycle.mark_failed(db, repo, error_msg)
        await jobs_service.fail_job(db, job, error_msg)
        raise
