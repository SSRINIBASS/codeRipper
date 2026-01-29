"""
Repo Intelligence Platform - Application Configuration

This module provides centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "repo-intelligence"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/repo_intelligence",
        description="Async PostgreSQL connection URL",
    )

    # Storage
    storage_path: Path = Field(
        default=Path("./data"),
        description="Base path for file storage (repos, indexes)",
    )

    # Hugging Face
    huggingface_api_key: str = Field(
        default="",
        description="Hugging Face API key for text generation",
    )
    embedding_model: str = "all-MiniLM-L6-v2"  # Local sentence-transformers model
    llm_model: str = "mistralai/Mistral-7B-Instruct-v0.2"  # HF Inference API model

    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for JWT signing",
    )
    api_key_header: str = "X-API-Key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # Rate Limiting
    rate_limit_per_minute: int = 100

    # Repository Limits
    max_repo_size_mb: int = 200
    max_files: int = 10000
    max_file_size_mb: int = 2
    max_indexing_minutes: int = 10
    max_chunks: int = 50000

    # Vector Search
    similarity_threshold: float = 0.65
    search_top_k: int = 10

    # Tutor
    max_conversation_tokens: int = 500
    max_conversation_history: int = 5
    session_ttl_hours: int = 24

    @field_validator("storage_path", mode="before")
    @classmethod
    def create_storage_path(cls, v: str | Path) -> Path:
        """Ensure storage path exists."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        (path / "repos").mkdir(exist_ok=True)
        (path / "indexes").mkdir(exist_ok=True)
        return path

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def repos_path(self) -> Path:
        """Path to cloned repositories."""
        return self.storage_path / "repos"

    @property
    def indexes_path(self) -> Path:
        """Path to FAISS indexes."""
        return self.storage_path / "indexes"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
