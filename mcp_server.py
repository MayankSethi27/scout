#!/usr/bin/env python3
"""
HTTP Server - Code Retrieval API for GitHub Repositories.

This FastAPI server provides network-accessible code retrieval capabilities.
It handles repository cloning, code indexing, and semantic search,
returning structured code context that clients can use.

FULLY LOCAL:
- No API keys required
- No network calls for embeddings
- Uses sentence-transformers/all-MiniLM-L6-v2 for local embeddings

Run with:
    python mcp_server.py

Or with uvicorn directly:
    uvicorn mcp_server:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /analyze_repo - Analyze a GitHub repository
    GET /health - Health check
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
import uvicorn

# Import core services (all local, no API keys)
from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService, EmbeddingConfig
from app.services.vector_store import VectorStore, VectorStoreConfig
from app.services.repo_service import RepoService, RepoServiceConfig
from app.services.indexing_service import IndexingService, IndexingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_code_retrieval")


# =============================================================================
# SERVICE INITIALIZATION (Fully Local - No API Keys)
# =============================================================================

_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_repo_service: RepoService | None = None
_indexing_service: IndexingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service (fully local, no API)."""
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


def get_vector_store() -> VectorStore:
    """Get or create vector store."""
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


def get_repo_service() -> RepoService:
    """Get or create repository service."""
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


def get_indexing_service() -> IndexingService:
    """Get or create indexing service."""
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


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class AnalyzeRepoRequest(BaseModel):
    """Request schema for the /analyze_repo endpoint."""
    repo_url: str = Field(
        ...,
        description="GitHub repository URL (e.g., https://github.com/owner/repo)",
        min_length=10,
    )
    query: str = Field(
        ...,
        description="Question or search query to find relevant code",
        min_length=3,
        max_length=1000,
        alias="question"
    )
    top_k: int = Field(
        default=10,
        description="Number of code snippets to retrieve (1-30)",
        ge=1,
        le=30,
    )

    class Config:
        populate_by_name = True


class CodeSnippet(BaseModel):
    """A retrieved code snippet with full context."""
    file_path: str = Field(..., description="Path to the file in the repository")
    content: str = Field(..., description="The code content")
    start_line: int | None = Field(None, description="Starting line number (1-indexed)")
    end_line: int | None = Field(None, description="Ending line number (1-indexed)")
    language: str = Field("", description="Programming language")
    relevance_score: float = Field(..., description="Semantic similarity score (0-1)")
    chunk_index: int = Field(0, description="Index of this chunk within the file")


class RepositoryInfo(BaseModel):
    """Information about the repository."""
    url: str
    owner: str
    name: str
    local_path: str | None = None
    total_files_indexed: int = 0
    total_chunks: int = 0


class AnalyzeRepoResponse(BaseModel):
    """
    Response schema - structured code context for clients.

    This output contains raw code snippets and metadata.
    Clients should analyze this context to answer questions.
    """
    success: bool = Field(..., description="Whether retrieval completed successfully")
    repository: RepositoryInfo = Field(..., description="Repository information")
    query: str = Field(..., description="The search query used")
    code_snippets: list[CodeSnippet] = Field(
        default_factory=list,
        description="Retrieved code snippets ranked by relevance"
    )
    total_results: int = Field(0, description="Total number of snippets retrieved")
    error: str | None = Field(None, description="Error message if failed")
    retrieval_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the retrieval process"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = ""
    embedding_model: str = ""
    fully_local: bool = True


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} HTTP Server v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Embedding model: {settings.embedding_model} (local)")
    logger.info("Mode: Fully local - no API keys required")

    # Pre-initialize services on startup (optional, lazy loading works too)
    logger.info("Pre-initializing services...")
    get_embedding_service()
    get_vector_store()
    get_repo_service()
    get_indexing_service()
    logger.info("Services initialized successfully")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down HTTP server...")


# Create FastAPI application
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Network-accessible GitHub code retrieval API. Fully local - no API keys required.",
    version=settings.app_version,
    lifespan=lifespan,
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for network accessibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API ENDPOINTS
# =============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns server status and configuration info.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        embedding_model=settings.embedding_model,
        fully_local=True
    )


@app.post("/analyze_repo", response_model=AnalyzeRepoResponse)
async def analyze_repo(request: AnalyzeRepoRequest):
    """
    Analyze a GitHub repository and retrieve relevant code snippets.

    This endpoint:
    1. Clones/caches the repository
    2. Indexes code (if not already indexed)
    3. Performs semantic search
    4. Returns structured code context

    FULLY LOCAL - No API calls, no network for embeddings.
    """
    start_time = datetime.utcnow()

    # Handle both 'query' and 'question' field names
    query_text = request.query

    logger.info(f"Retrieving code from: {request.repo_url}")
    logger.info(f"Query: {query_text[:100]}...")

    # Get services
    repo_service = get_repo_service()
    indexing_service = get_indexing_service()
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()

    # Parse repository URL
    try:
        repo_info = repo_service.parse_github_url(request.repo_url)
    except ValueError as e:
        return AnalyzeRepoResponse(
            success=False,
            repository=RepositoryInfo(url=request.repo_url, owner="", name=""),
            query=query_text,
            error=f"Invalid repository URL: {e}"
        )

    # Index repository if needed
    index_stats = {"total_files": 0, "total_chunks": 0}
    if not indexing_service.is_indexed(request.repo_url):
        logger.info("Repository not indexed, starting indexing...")
        index_result = await indexing_service.index_repository(request.repo_url)

        if not index_result.success:
            return AnalyzeRepoResponse(
                success=False,
                repository=RepositoryInfo(
                    url=request.repo_url,
                    owner=repo_info.owner,
                    name=repo_info.name
                ),
                query=query_text,
                error=f"Indexing failed: {'; '.join(index_result.errors)}"
            )

        index_stats = {
            "total_files": index_result.indexed_files,
            "total_chunks": index_result.total_chunks
        }
        logger.info(f"Indexed {index_result.indexed_files} files, {index_result.total_chunks} chunks")

    # Perform semantic search
    logger.info(f"Searching for relevant code (top_k={request.top_k})...")
    query_embedding = await embedding_service.embed(query_text)

    raw_results = await vector_store.search(
        embedding=query_embedding,
        top_k=request.top_k
    )

    # Convert to structured snippets
    code_snippets = []
    for result in raw_results:
        metadata = result.get("metadata", {})
        snippet = CodeSnippet(
            file_path=metadata.get("file_path", "unknown"),
            content=result.get("content", ""),
            start_line=metadata.get("start_line"),
            end_line=metadata.get("end_line"),
            language=metadata.get("language", ""),
            relevance_score=round(result.get("score", 0), 4),
            chunk_index=metadata.get("chunk_index", 0)
        )
        code_snippets.append(snippet)

    # Calculate duration
    duration = (datetime.utcnow() - start_time).total_seconds()

    # Build response
    settings = get_settings()
    response = AnalyzeRepoResponse(
        success=True,
        repository=RepositoryInfo(
            url=request.repo_url,
            owner=repo_info.owner,
            name=repo_info.name,
            total_files_indexed=index_stats.get("total_files", 0),
            total_chunks=index_stats.get("total_chunks", 0)
        ),
        query=query_text,
        code_snippets=code_snippets,
        total_results=len(code_snippets),
        retrieval_metadata={
            "duration_seconds": round(duration, 2),
            "top_k_requested": request.top_k,
            "embedding_model": settings.embedding_model,
            "fully_local": True,
        }
    )

    logger.info(f"Retrieved {len(code_snippets)} snippets in {duration:.2f}s")

    return response


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """Main entry point for the HTTP server."""
    settings = get_settings()

    host = settings.server_host
    port = settings.server_port

    logger.info(f"Starting HTTP server on {host}:{port}")
    logger.info(f"API Documentation: http://{host}:{port}/docs")

    uvicorn.run(
        "mcp_server:app",
        host=host,
        port=port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()
