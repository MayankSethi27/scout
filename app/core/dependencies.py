"""
Dependencies - Dependency injection for services and components.

Provides singleton instances of services.

NOTE: The MCP server (mcp_server.py) has its own service initialization.
This file is primarily for the deprecated REST API.
"""

from typing import Dict, Any
from functools import lru_cache
import uuid

from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService, EmbeddingConfig
from app.services.vector_store import VectorStore, VectorStoreConfig
from app.services.repo_service import RepoService, RepoServiceConfig
from app.services.indexing_service import IndexingService, IndexingConfig


class SessionManager:
    """
    Manages analysis sessions for follow-up questions.

    Stores context between requests to enable conversational analysis.
    """

    def __init__(self):
        self._sessions: Dict[str, Any] = {}

    def create_session(self, repo_url: str, context: Any) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())[:8]
        self._sessions[session_id] = {
            "repo_url": repo_url,
            "context": context,
            "question_count": 0
        }
        return session_id

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, context: Any) -> None:
        """Update session context."""
        if session_id in self._sessions:
            self._sessions[session_id]["context"] = context
            self._sessions[session_id]["question_count"] += 1

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# Singleton instances
_embedding_service = None
_vector_store = None
_repo_service = None
_indexing_service = None
_session_manager = None


@lru_cache()
def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance (fully local, no API keys)."""
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        config = EmbeddingConfig(
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            device=settings.embedding_device
        )
        _embedding_service = EmbeddingService(config=config)
    return _embedding_service


@lru_cache()
def get_vector_store() -> VectorStore:
    """Get vector store instance."""
    global _vector_store
    if _vector_store is None:
        settings = get_settings()
        config = VectorStoreConfig(
            backend=settings.vector_store_backend,
            collection_name=settings.vector_store_collection,
            persist_directory=settings.vector_store_path
        )
        _vector_store = VectorStore(config=config)
    return _vector_store


@lru_cache()
def get_repo_service() -> RepoService:
    """Get repository service instance."""
    global _repo_service
    if _repo_service is None:
        settings = get_settings()
        config = RepoServiceConfig(
            storage_path=settings.repo_storage_path,
            cache_ttl_hours=settings.repo_cache_ttl_hours,
            max_repo_size_mb=settings.repo_max_size_mb
        )
        _repo_service = RepoService(config=config)
    return _repo_service


@lru_cache()
def get_indexing_service() -> IndexingService:
    """Get indexing service instance."""
    global _indexing_service
    if _indexing_service is None:
        settings = get_settings()
        config = IndexingConfig(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            max_file_size_kb=settings.max_file_size_kb,
            batch_size=settings.indexing_batch_size
        )
        _indexing_service = IndexingService(
            embedding_service=get_embedding_service(),
            vector_store=get_vector_store(),
            repo_service=get_repo_service(),
            config=config
        )
    return _indexing_service


def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
