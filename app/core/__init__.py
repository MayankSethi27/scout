"""
Core Module - Configuration and dependency injection.
"""

from app.core.config import Settings, get_settings, settings
from app.core.dependencies import (
    get_embedding_service,
    get_vector_store,
    get_repo_service,
    get_indexing_service,
    get_session_manager,
)

__all__ = [
    "Settings",
    "get_settings",
    "settings",
    "get_embedding_service",
    "get_vector_store",
    "get_repo_service",
    "get_indexing_service",
    "get_session_manager",
]
