"""
Background Job Worker - Processes async jobs from the queue.
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager

import structlog

from app.config import get_settings
from app.database import get_db_session, init_db
from app.models import Job, JobStatus, JobType
from app.services import get_pending_jobs, get_repository
from app.services.documentation import execute_docs_generation
from app.services.indexing import execute_indexing
from app.services.ingestion import execute_ingestion

settings = get_settings()
logger = structlog.get_logger(__name__)

# Worker state
_running = True


def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _running
    _running = False
    logger.info("shutdown_signal_received", signal=signum)


async def process_job(job: Job) -> None:
    """Process a single job based on its type."""
    async with get_db_session() as db:
        try:
            # Refetch job and repo in this session to avoid detached instance errors
            from app.services import get_job
            job = await get_job(db, job.id)
            repo = await get_repository(db, job.repo_id)
            
            if job.type == JobType.INGEST.value:
                await execute_ingestion(db, repo, job)
            elif job.type == JobType.INDEX.value:
                await execute_indexing(db, repo, job)
            elif job.type == JobType.DOCS.value:
                await execute_docs_generation(db, repo, job)
            else:
                await logger.awarning("unknown_job_type", job_id=job.id, type=job.type)
                
        except Exception as e:
            await logger.aerror(
                "job_processing_error",
                job_id=job.id,
                error=str(e),
            )


async def worker_loop(
    poll_interval: float = 5.0,
    max_concurrent: int = 2,
) -> None:
    """
    Main worker loop that polls for and processes jobs.
    
    Args:
        poll_interval: Seconds between queue polls
        max_concurrent: Maximum concurrent jobs
    """
    global _running
    
    await logger.ainfo(
        "worker_started",
        poll_interval=poll_interval,
        max_concurrent=max_concurrent,
    )
    
    active_tasks: set[asyncio.Task] = set()
    
    while _running:
        try:
            # Clean up completed tasks
            completed = {t for t in active_tasks if t.done()}
            for task in completed:
                try:
                    await task
                except Exception as e:
                    await logger.aerror("task_error", error=str(e))
            active_tasks -= completed
            
            # Check capacity
            if len(active_tasks) >= max_concurrent:
                await asyncio.sleep(poll_interval)
                continue
            
            # Fetch pending jobs
            async with get_db_session() as db:
                jobs = await get_pending_jobs(
                    db, limit=max_concurrent - len(active_tasks)
                )
            
            if not jobs:
                await asyncio.sleep(poll_interval)
                continue
            
            # Start jobs
            for job in jobs:
                await logger.ainfo(
                    "starting_job",
                    job_id=job.id,
                    type=job.type,
                )
                task = asyncio.create_task(process_job(job))
                active_tasks.add(task)
                
        except Exception as e:
            await logger.aerror("worker_loop_error", error=str(e))
            await asyncio.sleep(poll_interval)
    
    # Wait for remaining tasks on shutdown
    if active_tasks:
        await logger.ainfo("waiting_for_active_tasks", count=len(active_tasks))
        await asyncio.gather(*active_tasks, return_exceptions=True)
    
    await logger.ainfo("worker_stopped")


async def main() -> None:
    """Main entry point for the worker."""
    # Configure structured logging
    import logging
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    await logger.ainfo("initializing_worker")
    
    # Initialize database
    await init_db()
    
    try:
        await worker_loop()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
