"""
Search Service - Semantic search over indexed code.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.llm import generate_embedding
from app.core.vector_store import VectorStore
from app.models import CodeChunk
from app.schemas import SearchResult
from app.services import check_api_readiness

settings = get_settings()
logger = structlog.get_logger(__name__)


async def search_code(
    db: AsyncSession,
    repo_id: str,
    query: str,
    limit: int = 10,
    offset: int = 0,
    min_score: float | None = None,
    file_filter: str | None = None,
) -> tuple[list[SearchResult], int]:
    """
    Perform semantic search over indexed code.
    
    Args:
        db: Database session
        repo_id: Repository ID
        query: Natural language query
        limit: Maximum results
        offset: Result offset
        min_score: Minimum similarity threshold
        file_filter: Optional glob pattern for file filtering
        
    Returns:
        Tuple of (results, total_count)
    """
    # Check readiness
    await check_api_readiness(db, repo_id, "search")
    
    threshold = min_score or settings.similarity_threshold
    
    # Generate query embedding
    query_embedding = await generate_embedding(query)
    
    # Load vector store
    vector_store = VectorStore(repo_id)
    if not vector_store.load():
        await logger.awarning("vector_store_not_found", repo_id=repo_id)
        return [], 0
    
    # Search with extra results for filtering
    search_results = vector_store.search(
        query_embedding,
        top_k=limit + offset + 50,  # Extra for filtering
        threshold=threshold,
    )
    
    if not search_results:
        return [], 0
    
    # Get chunk IDs
    chunk_ids = [
        vector_store.get_chunk_id(r.index)
        for r in search_results
        if vector_store.get_chunk_id(r.index)
    ]
    
    # Fetch chunks from database
    result = await db.execute(
        select(CodeChunk).where(CodeChunk.id.in_(chunk_ids))
    )
    chunks_by_id = {c.id: c for c in result.scalars().all()}
    
    # Build results
    results = []
    for search_result in search_results:
        chunk_id = vector_store.get_chunk_id(search_result.index)
        if not chunk_id or chunk_id not in chunks_by_id:
            continue
        
        chunk = chunks_by_id[chunk_id]
        
        # Apply file filter if specified
        if file_filter:
            import fnmatch
            if not fnmatch.fnmatch(chunk.file_path, file_filter):
                continue
        
        results.append(
            SearchResult(
                file_path=chunk.file_path,
                symbol=chunk.symbol_name,
                symbol_type=chunk.symbol_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                score=search_result.score,
                language=chunk.language,
            )
        )
    
    total = len(results)
    
    # Apply pagination
    results = results[offset : offset + limit]
    
    await logger.ainfo(
        "search_completed",
        repo_id=repo_id,
        query=query[:50],
        results=len(results),
        total=total,
    )
    
    return results, total
