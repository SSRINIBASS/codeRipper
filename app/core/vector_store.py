"""
Vector Store - FAISS abstraction for semantic search.
"""

import json
import pickle
from pathlib import Path
from typing import NamedTuple

import faiss
import numpy as np

from app.config import get_settings

settings = get_settings()

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384


class SearchResult(NamedTuple):
    """Vector search result."""

    index: int
    score: float


class VectorStore:
    """
    FAISS-based vector store with persistence.
    
    Provides an abstraction over FAISS for semantic search
    with save/load functionality.
    """

    def __init__(self, repo_id: str, dimension: int = EMBEDDING_DIM):
        """
        Initialize vector store for a repository.
        
        Args:
            repo_id: Repository identifier
            dimension: Embedding dimension
        """
        self.repo_id = repo_id
        self.dimension = dimension
        self.index: faiss.IndexFlatIP | None = None
        self.id_map: list[str] = []  # Maps FAISS index to chunk IDs
        
        self._index_path = settings.indexes_path / repo_id / "index.faiss"
        self._map_path = settings.indexes_path / repo_id / "id_map.json"

    def create_index(self) -> None:
        """Create a new empty index using Inner Product (cosine similarity)."""
        # Using IndexFlatIP for inner product (cosine similarity on normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.id_map = []

    def add_embeddings(
        self,
        embeddings: list[list[float]],
        chunk_ids: list[str],
    ) -> None:
        """
        Add embeddings to the index.
        
        Args:
            embeddings: List of embedding vectors
            chunk_ids: Corresponding chunk IDs
        """
        if self.index is None:
            self.create_index()
        
        # Convert to numpy and normalize for cosine similarity
        vectors = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors)
        
        # Add to index
        self.index.add(vectors)
        self.id_map.extend(chunk_ids)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        threshold: float = 0.65,
    ) -> list[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of SearchResult with index and score
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Normalize query vector
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        
        # Search
        scores, indices = self.index.search(query, min(top_k, self.index.ntotal))
        
        # Filter by threshold and convert to results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and score >= threshold:
                results.append(SearchResult(index=int(idx), score=float(score)))
        
        return results

    def get_chunk_id(self, index: int) -> str | None:
        """Get chunk ID for a FAISS index."""
        if 0 <= index < len(self.id_map):
            return self.id_map[index]
        return None

    def save(self) -> None:
        """Save index and mappings to disk."""
        if self.index is None:
            return
        
        # Ensure directory exists
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        faiss.write_index(self.index, str(self._index_path))
        
        # Save ID map
        with open(self._map_path, "w") as f:
            json.dump(self.id_map, f)

    def load(self) -> bool:
        """
        Load index and mappings from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self._index_path.exists() or not self._map_path.exists():
            return False
        
        try:
            # Load FAISS index
            self.index = faiss.read_index(str(self._index_path))
            
            # Load ID map
            with open(self._map_path) as f:
                self.id_map = json.load(f)
            
            return True
        except Exception:
            return False

    def delete(self) -> bool:
        """
        Delete index files from disk.
        
        Returns:
            True if deleted, False if not found
        """
        deleted = False
        if self._index_path.exists():
            self._index_path.unlink()
            deleted = True
        if self._map_path.exists():
            self._map_path.unlink()
            deleted = True
        
        # Clean up empty directory
        if self._index_path.parent.exists():
            try:
                self._index_path.parent.rmdir()
            except OSError:
                pass  # Directory not empty
        
        return deleted

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        if self.index is None:
            return 0
        return self.index.ntotal
