"""
Code Chunking - Extract logical code units for indexing.

Supports multiple languages with Tree-sitter fallback to sliding window.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from app.config import get_settings
from app.core.llm import count_tokens

settings = get_settings()

# Language detection by extension
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".txt": "text",
}

# Files to skip during chunking
SKIP_PATTERNS = [
    r"\.git/",
    r"node_modules/",
    r"__pycache__/",
    r"\.pyc$",
    r"\.pyo$",
    r"\.egg-info/",
    r"\.so$",
    r"\.dll$",
    r"\.exe$",
    r"\.bin$",
    r"\.lock$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"\.min\.js$",
    r"\.min\.css$",
    r"\.map$",
    r"\.whl$",
    r"\.tar\.gz$",
    r"\.zip$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.gif$",
    r"\.ico$",
    r"\.svg$",
    r"\.pdf$",
    r"\.woff",
    r"\.ttf$",
]


@dataclass
class CodeChunk:
    """A chunk of code extracted from a file."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str | None = None
    symbol_type: str | None = None
    symbol_name: str | None = None
    token_count: int | None = None


def detect_language(file_path: Path) -> str | None:
    """Detect programming language from file extension."""
    return LANGUAGE_MAP.get(file_path.suffix.lower())


def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped during chunking."""
    path_str = str(file_path)
    return any(re.search(pattern, path_str) for pattern in SKIP_PATTERNS)


def read_file_safe(file_path: Path) -> str | None:
    """
    Safely read file content, handling encoding issues.
    
    Returns None if file cannot be read or is binary.
    """
    try:
        # Check file size
        if file_path.stat().st_size > settings.max_file_size_mb * 1024 * 1024:
            return None
        
        # Try UTF-8 first
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try latin-1 as fallback
            try:
                return file_path.read_text(encoding="latin-1")
            except UnicodeDecodeError:
                return None
    except (OSError, PermissionError):
        return None


def sliding_window_chunk(
    content: str,
    file_path: str,
    language: str | None,
    max_tokens: int = 1500,
    overlap_tokens: int = 200,
) -> Generator[CodeChunk, None, None]:
    """
    Chunk content using sliding window approach.
    
    Args:
        content: File content
        file_path: Path to file
        language: Detected language
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between chunks
        
    Yields:
        CodeChunk objects
    """
    lines = content.split("\n")
    
    if not lines:
        return
    
    current_chunk_lines: list[str] = []
    current_start_line = 1
    current_tokens = 0
    
    for i, line in enumerate(lines, 1):
        line_tokens = count_tokens(line)
        
        # Check if adding this line exceeds max tokens
        if current_tokens + line_tokens > max_tokens and current_chunk_lines:
            # Yield current chunk
            chunk_content = "\n".join(current_chunk_lines)
            yield CodeChunk(
                file_path=file_path,
                start_line=current_start_line,
                end_line=i - 1,
                content=chunk_content,
                language=language,
                token_count=current_tokens,
            )
            
            # Start new chunk with overlap
            overlap_lines = []
            overlap_tokens_count = 0
            for prev_line in reversed(current_chunk_lines):
                prev_tokens = count_tokens(prev_line)
                if overlap_tokens_count + prev_tokens > overlap_tokens:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_tokens_count += prev_tokens
            
            current_chunk_lines = overlap_lines
            current_start_line = i - len(overlap_lines)
            current_tokens = overlap_tokens_count
        
        current_chunk_lines.append(line)
        current_tokens += line_tokens
    
    # Yield final chunk
    if current_chunk_lines:
        chunk_content = "\n".join(current_chunk_lines)
        yield CodeChunk(
            file_path=file_path,
            start_line=current_start_line,
            end_line=len(lines),
            content=chunk_content,
            language=language,
            token_count=current_tokens,
        )


def extract_python_symbols(
    content: str,
    file_path: str,
) -> Generator[CodeChunk, None, None]:
    """
    Extract Python functions and classes as chunks.
    
    Uses regex-based extraction as a lightweight alternative to AST parsing.
    """
    lines = content.split("\n")
    
    # Pattern for function and class definitions
    class_pattern = re.compile(r"^class\s+(\w+)")
    func_pattern = re.compile(r"^(?:async\s+)?def\s+(\w+)")
    
    current_symbol: dict | None = None
    current_lines: list[str] = []
    current_indent = 0
    
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        
        # Check for new symbol at base level or class level
        class_match = class_pattern.match(stripped)
        func_match = func_pattern.match(stripped)
        
        if class_match or func_match:
            # Yield previous symbol if exists
            if current_symbol and current_lines:
                yield CodeChunk(
                    file_path=file_path,
                    start_line=current_symbol["start"],
                    end_line=i - 1,
                    content="\n".join(current_lines),
                    language="python",
                    symbol_type=current_symbol["type"],
                    symbol_name=current_symbol["name"],
                    token_count=count_tokens("\n".join(current_lines)),
                )
            
            if class_match:
                current_symbol = {
                    "type": "class",
                    "name": class_match.group(1),
                    "start": i,
                }
            else:
                current_symbol = {
                    "type": "function",
                    "name": func_match.group(1),
                    "start": i,
                }
            current_lines = [line]
            current_indent = indent
        elif current_symbol:
            # Continue current symbol if indented or blank line
            if stripped == "" or indent > current_indent:
                current_lines.append(line)
            elif indent == current_indent and not (class_match or func_match):
                # Decorator or continuation
                current_lines.append(line)
            else:
                # Symbol ended
                yield CodeChunk(
                    file_path=file_path,
                    start_line=current_symbol["start"],
                    end_line=i - 1,
                    content="\n".join(current_lines),
                    language="python",
                    symbol_type=current_symbol["type"],
                    symbol_name=current_symbol["name"],
                    token_count=count_tokens("\n".join(current_lines)),
                )
                current_symbol = None
                current_lines = []
    
    # Yield final symbol
    if current_symbol and current_lines:
        yield CodeChunk(
            file_path=file_path,
            start_line=current_symbol["start"],
            end_line=len(lines),
            content="\n".join(current_lines),
            language="python",
            symbol_type=current_symbol["type"],
            symbol_name=current_symbol["name"],
            token_count=count_tokens("\n".join(current_lines)),
        )


def chunk_file(file_path: Path, base_path: Path) -> Generator[CodeChunk, None, None]:
    """
    Chunk a single file into logical units.
    
    Args:
        file_path: Absolute path to file
        base_path: Base repository path for relative paths
        
    Yields:
        CodeChunk objects
    """
    if should_skip_file(file_path):
        return
    
    content = read_file_safe(file_path)
    if not content:
        return
    
    # Skip very small files
    if len(content.strip()) < 50:
        return
    
    relative_path = str(file_path.relative_to(base_path))
    language = detect_language(file_path)
    
    # Use language-specific extraction when available
    if language == "python":
        chunks = list(extract_python_symbols(content, relative_path))
        if chunks:
            yield from chunks
            return
    
    # Fall back to sliding window
    yield from sliding_window_chunk(content, relative_path, language)


def chunk_repository(repo_path: Path) -> Generator[CodeChunk, None, None]:
    """
    Chunk all files in a repository.
    
    Args:
        repo_path: Path to cloned repository
        
    Yields:
        CodeChunk objects for all files
    """
    file_count = 0
    chunk_count = 0
    
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        
        if should_skip_file(file_path):
            continue
        
        file_count += 1
        if file_count > settings.max_files:
            break
        
        for chunk in chunk_file(file_path, repo_path):
            chunk_count += 1
            if chunk_count > settings.max_chunks:
                return
            yield chunk
