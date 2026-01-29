"""
Git Utilities - Repository cloning and analysis.
"""

import re
import shutil
from pathlib import Path
from typing import NamedTuple

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from app.config import get_settings
from app.core.errors import InvalidRepoURLError, RepoTooLargeError

settings = get_settings()


class RepoInfo(NamedTuple):
    """Parsed repository information."""

    owner: str
    name: str
    url: str


def parse_github_url(url: str) -> RepoInfo:
    """
    Parse a GitHub URL and extract owner and repo name.
    
    Args:
        url: GitHub repository URL
        
    Returns:
        RepoInfo with owner, name, and normalized URL
        
    Raises:
        InvalidRepoURLError: If URL is not a valid GitHub URL
    """
    # Normalize URL
    url = url.strip().rstrip("/")
    
    # Remove .git suffix if present
    if url.endswith(".git"):
        url = url[:-4]
    
    # Match patterns
    patterns = [
        r"https?://github\.com/([^/]+)/([^/]+)",
        r"git@github\.com:([^/]+)/([^/]+)",
    ]
    
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, name = match.groups()
            return RepoInfo(
                owner=owner,
                name=name,
                url=f"https://github.com/{owner}/{name}",
            )
    
    raise InvalidRepoURLError(url, "Could not parse GitHub URL")


async def clone_repository(
    url: str,
    repo_id: str,
    shallow: bool = True,
) -> tuple[Path, str]:
    """
    Clone a repository to local storage.
    
    Args:
        url: Repository URL
        repo_id: Unique identifier for local storage
        shallow: Whether to use shallow clone (default True)
        
    Returns:
        Tuple of (clone_path, commit_hash)
        
    Raises:
        InvalidRepoURLError: If cloning fails
        RepoTooLargeError: If repository exceeds size limits
    """
    clone_path = settings.repos_path / repo_id
    
    # Remove existing if present
    if clone_path.exists():
        shutil.rmtree(clone_path)
    
    try:
        # Clone with depth=1 for shallow clone
        clone_kwargs = {}
        if shallow:
            clone_kwargs["depth"] = 1
        
        repo = Repo.clone_from(url, clone_path, **clone_kwargs)
        
        # Get commit hash
        commit_hash = repo.head.commit.hexsha
        
        # Check size
        size_bytes = get_directory_size(clone_path)
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > settings.max_repo_size_mb:
            # Clean up
            shutil.rmtree(clone_path)
            raise RepoTooLargeError(size_mb, settings.max_repo_size_mb)
        
        return clone_path, commit_hash
        
    except GitCommandError as e:
        # Clean up on failure
        if clone_path.exists():
            shutil.rmtree(clone_path)
        raise InvalidRepoURLError(url, f"Git clone failed: {e}")
    except InvalidGitRepositoryError:
        if clone_path.exists():
            shutil.rmtree(clone_path)
        raise InvalidRepoURLError(url, "Invalid git repository")


def get_directory_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except (OSError, PermissionError):
                pass
    return total


def get_file_count(path: Path) -> int:
    """Count total files in a directory."""
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
    return count


def delete_repository(repo_id: str) -> bool:
    """
    Delete a cloned repository.
    
    Args:
        repo_id: Repository identifier
        
    Returns:
        True if deleted, False if not found
    """
    clone_path = settings.repos_path / repo_id
    if clone_path.exists():
        shutil.rmtree(clone_path)
        return True
    return False
