"""
Application Configuration - Environment settings and constants.

Loads configuration from environment variables with sensible defaults.
Uses Pydantic Settings for validation and type safety.

FULLY LOCAL - No API keys required.
"""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Usage:
        from app.core.config import get_settings
        settings = get_settings()
    """

    # Application
    app_name: str = "GitHub Code Retrieval"
    app_version: str = "2.0.0"
    debug: bool = False
    environment: str = "development"

    # HTTP Server Configuration
    server_host: str = "0.0.0.0"  # Bind to all interfaces for network access
    server_port: int = 8000  # Default port

    # Embedding Configuration (Local - no API keys)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384  # all-MiniLM-L6-v2 produces 384-dim vectors
    embedding_device: str = "cpu"  # "cpu", "cuda", or "mps"

    # Vector Store Configuration
    vector_store_backend: str = "chroma"  # chroma or memory
    vector_store_path: str = "./data/vector_db"
    vector_store_collection: str = "codebase"

    # Repository Configuration
    repo_storage_path: str = "./data/repos"
    repo_cache_ttl_hours: int = 24
    repo_max_size_mb: int = 500

    # Indexing Configuration
    chunk_size: int = 1500
    chunk_overlap: int = 200
    max_file_size_kb: int = 500
    indexing_batch_size: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Convenience access
settings = get_settings()
