"""
Services Layer for GitHub Codebase Analyst
==========================================

Services handle the core business logic and external integrations:

- EmbeddingService: Generates vector embeddings from text/code
- VectorStore: Stores and searches embeddings (ChromaDB/Pinecone)
- RepoService: Manages repository operations
- IndexingService: Orchestrates the indexing pipeline

DEPENDENCY FLOW:
----------------
    EmbeddingService ──┐
                       ├──► IndexingService
    VectorStore ───────┘
         │
         └──► Used by Search Tool
"""

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.repo_service import RepoService
from app.services.indexing_service import IndexingService

__all__ = [
    "EmbeddingService",
    "VectorStore",
    "RepoService",
    "IndexingService",
]
