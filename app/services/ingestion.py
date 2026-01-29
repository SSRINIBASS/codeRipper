"""
Ingestion Service - Repository cloning and structure analysis.
"""

import asyncio
from pathlib import Path
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.chunking import LANGUAGE_MAP, detect_language, should_skip_file
from app.core.git import (
    clone_repository,
    get_directory_size,
    get_file_count,
    parse_github_url,
)
from app.models import Job, JobType, Repository, RepoStatus
from app.schemas import EntryPoint, FileNode
from app.services import jobs as jobs_service
from app.services import lifecycle

settings = get_settings()
logger = structlog.get_logger(__name__)


# Entry point patterns by language
ENTRY_POINT_PATTERNS = {
    "python": [
        ("main.py", "main", 0.9, "Common Python entry point"),
        ("app.py", "app", 0.85, "Flask/FastAPI application"),
        ("__main__.py", "main", 0.95, "Python package entry point"),
        ("manage.py", "cli", 0.8, "Django management script"),
        ("setup.py", "setup", 0.7, "Package setup script"),
        ("cli.py", "cli", 0.8, "CLI entry point"),
        ("run.py", "main", 0.75, "Run script"),
    ],
    "javascript": [
        ("index.js", "main", 0.85, "Node.js entry point"),
        ("app.js", "app", 0.85, "Express application"),
        ("main.js", "main", 0.8, "Main entry point"),
        ("server.js", "server", 0.85, "Server entry point"),
        ("src/index.js", "main", 0.9, "Source entry point"),
    ],
    "typescript": [
        ("index.ts", "main", 0.85, "TypeScript entry point"),
        ("app.ts", "app", 0.85, "Application entry point"),
        ("main.ts", "main", 0.8, "Main entry point"),
        ("src/index.ts", "main", 0.9, "Source entry point"),
    ],
    "go": [
        ("main.go", "main", 0.95, "Go main entry point"),
        ("cmd/main.go", "main", 0.9, "Command entry point"),
    ],
    "rust": [
        ("src/main.rs", "main", 0.95, "Rust binary entry point"),
        ("src/lib.rs", "lib", 0.85, "Rust library entry point"),
    ],
    "java": [
        ("Main.java", "main", 0.8, "Java main class"),
        ("Application.java", "app", 0.85, "Spring application"),
        ("App.java", "main", 0.8, "Application class"),
    ],
}


async def ingest_repository(
    db: AsyncSession,
    repo_url: str,
    force: bool = False,
) -> tuple[Repository, Job]:
    """
    Start repository ingestion process.
    
    Args:
        db: Database session
        repo_url: GitHub repository URL
        force: Force re-ingestion if exists
        
    Returns:
        Tuple of (Repository, Job)
    """
    # Parse URL
    repo_info = parse_github_url(repo_url)
    
    # Check for existing
    existing = await lifecycle.get_repository_by_url(db, repo_info.url)
    
    if existing and not force:
        # Return existing with status
        jobs = await jobs_service.get_jobs_for_repo(db, existing.id)
        latest_job = jobs[0] if jobs else None
        
        if latest_job:
            return existing, latest_job
        
        # Create new job if none exists
        job = await jobs_service.create_job(db, existing.id, JobType.INGEST)
        return existing, job
    
    if existing and force:
        # Reset existing repository
        existing.status = RepoStatus.CREATED.value
        existing.error_message = None
        await db.commit()
        repo = existing
    else:
        # Create new repository
        repo = Repository(
            id=str(uuid4()),
            repo_url=repo_info.url,
            name=repo_info.name,
            owner=repo_info.owner,
            status=RepoStatus.CREATED.value,
        )
        db.add(repo)
        await db.commit()
        await db.refresh(repo)
    
    # Create ingestion job
    job = await jobs_service.create_job(db, repo.id, JobType.INGEST)
    
    await logger.ainfo(
        "ingestion_started",
        repo_id=repo.id,
        repo_url=repo_info.url,
        job_id=job.id,
    )
    
    return repo, job


async def execute_ingestion(
    db: AsyncSession,
    repo: Repository,
    job: Job,
) -> Repository:
    """
    Execute the ingestion process (cloning and structure analysis).
    
    This should be called by the job worker.
    """
    try:
        # Start job
        await jobs_service.start_job(db, job)
        
        # Clone repository
        await jobs_service.update_progress(db, job, 10)
        clone_path, commit_hash = await clone_repository(repo.repo_url, repo.id)
        
        # Update repository with clone info
        repo.commit_hash = commit_hash
        await lifecycle.transition_status(db, repo, RepoStatus.CLONED)
        await jobs_service.update_progress(db, job, 40)
        
        # Analyze structure
        total_files, total_size, primary_language = await analyze_structure(clone_path)
        
        repo.total_files = total_files
        repo.total_size_bytes = total_size
        repo.primary_language = primary_language
        
        await lifecycle.transition_status(db, repo, RepoStatus.STRUCTURED)
        await jobs_service.update_progress(db, job, 100)
        
        # Complete job
        await jobs_service.complete_job(db, job)
        
        await logger.ainfo(
            "ingestion_completed",
            repo_id=repo.id,
            files=total_files,
            size_bytes=total_size,
            language=primary_language,
        )
        
        return repo
        
    except Exception as e:
        error_msg = str(e)
        await lifecycle.mark_failed(db, repo, error_msg)
        await jobs_service.fail_job(db, job, error_msg)
        raise


async def analyze_structure(repo_path: Path) -> tuple[int, int, str | None]:
    """
    Analyze repository structure.
    
    Returns:
        Tuple of (file_count, total_size_bytes, primary_language)
    """
    file_count = 0
    total_size = 0
    language_counts: dict[str, int] = {}
    
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        
        if should_skip_file(file_path):
            continue
        
        file_count += 1
        
        try:
            total_size += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        
        # Count languages
        lang = detect_language(file_path)
        if lang:
            language_counts[lang] = language_counts.get(lang, 0) + 1
    
    # Determine primary language
    primary_language = None
    if language_counts:
        primary_language = max(language_counts, key=lambda k: language_counts[k])
    
    return file_count, total_size, primary_language


def build_file_tree(repo_path: Path, max_depth: int = 10) -> list[FileNode]:
    """
    Build file tree structure for API response.
    
    Args:
        repo_path: Path to repository
        max_depth: Maximum depth to traverse
        
    Returns:
        List of FileNode representing the tree
    """
    def build_node(path: Path, depth: int = 0) -> FileNode | None:
        if depth > max_depth:
            return None
        
        if should_skip_file(path):
            return None
        
        relative = path.relative_to(repo_path)
        
        if path.is_file():
            try:
                size = path.stat().st_size
            except (OSError, PermissionError):
                size = 0
            
            return FileNode(
                name=path.name,
                path=str(relative),
                type="file",
                size=size,
                language=detect_language(path),
            )
        elif path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir()):
                    child_node = build_node(child, depth + 1)
                    if child_node:
                        children.append(child_node)
            except (OSError, PermissionError):
                pass
            
            return FileNode(
                name=path.name,
                path=str(relative),
                type="directory",
                children=children,
            )
        
        return None
    
    # Build top-level
    nodes = []
    try:
        for item in sorted(repo_path.iterdir()):
            node = build_node(item)
            if node:
                nodes.append(node)
    except (OSError, PermissionError):
        pass
    
    return nodes


def detect_entry_points(
    repo_path: Path,
    primary_language: str | None,
) -> list[EntryPoint]:
    """
    Detect probable entry points in the repository.
    
    Args:
        repo_path: Path to repository
        primary_language: Detected primary language
        
    Returns:
        List of EntryPoint objects sorted by confidence
    """
    entry_points: list[EntryPoint] = []
    
    # Get patterns for primary language
    patterns = ENTRY_POINT_PATTERNS.get(primary_language, [])
    
    # Also check common patterns
    all_patterns = patterns + [
        ("README.md", "readme", 0.5, "Documentation entry point"),
        ("Makefile", "build", 0.6, "Build entry point"),
        ("Dockerfile", "container", 0.6, "Container entry point"),
    ]
    
    for file_pattern, ep_type, confidence, reason in all_patterns:
        # Check if file exists
        file_path = repo_path / file_pattern
        if file_path.exists():
            entry_points.append(
                EntryPoint(
                    file_path=file_pattern,
                    type=ep_type,
                    confidence=confidence,
                    reason=reason,
                )
            )
    
    # Check for __main__ pattern in Python
    if primary_language == "python":
        for py_file in repo_path.rglob("*.py"):
            if should_skip_file(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                if 'if __name__ == "__main__"' in content or "if __name__ == '__main__'" in content:
                    relative = py_file.relative_to(repo_path)
                    entry_points.append(
                        EntryPoint(
                            file_path=str(relative),
                            type="main",
                            confidence=0.85,
                            reason="Contains if __name__ == '__main__' guard",
                        )
                    )
            except (OSError, UnicodeDecodeError):
                pass
    
    # Sort by confidence
    entry_points.sort(key=lambda ep: ep.confidence, reverse=True)
    
    # Remove duplicates
    seen = set()
    unique = []
    for ep in entry_points:
        if ep.file_path not in seen:
            seen.add(ep.file_path)
            unique.append(ep)
    
    return unique[:10]  # Top 10
