"""
Analysis Endpoints - Core API for codebase analysis.

==============================================================================
DEPRECATION NOTICE
==============================================================================
These REST API endpoints are DEPRECATED in favor of the MCP (Model Context
Protocol) server interface.

Instead of calling these HTTP endpoints, configure your MCP client (e.g., Cursor)
to use the `analyze_github_repo` tool directly.

Run the MCP server:
    python mcp_server.py

See README.md for complete MCP setup instructions.
==============================================================================

Legacy functionality (for backwards compatibility):
- Analyzing codebases and answering questions
- Indexing repositories
- Searching code
- Managing analysis sessions
"""

from fastapi import APIRouter, Depends, BackgroundTasks
from datetime import datetime
from typing import Optional

from app.core.dependencies import (
    get_orchestrator,
    get_indexing_service,
    get_repo_service,
    get_embedding_service,
    get_vector_store,
    get_session_manager,
    Orchestrator,
    SessionManager
)
from app.services.indexing_service import IndexingService
from app.services.repo_service import RepoService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.models.requests import (
    AnalyzeRequest,
    IndexRequest,
    SearchRequest,
    FollowUpRequest
)
from app.models.responses import (
    AnalyzeResponse,
    IndexResponse,
    SearchResponse,
    RepoStatusResponse,
    ErrorResponse
)
from app.models.schemas import AnalysisMetadata, SearchResult
from app.api.middleware.error_handler import (
    SessionNotFoundError,
    RepositoryNotFoundError,
    AnalysisError
)


router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze Codebase",
    description="Analyze a GitHub repository and answer a question about it",
    responses={
        200: {"description": "Analysis completed successfully"},
        404: {"model": ErrorResponse, "description": "Repository not found"},
        500: {"model": ErrorResponse, "description": "Analysis failed"}
    }
)
async def analyze_codebase(
    request: AnalyzeRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    indexing_service: IndexingService = Depends(get_indexing_service),
    session_manager: SessionManager = Depends(get_session_manager)
) -> AnalyzeResponse:
    """
    Analyze a codebase and answer a question.

    This endpoint:
    1. Clones the repository (if not cached)
    2. Indexes the code (if not already indexed)
    3. Searches for relevant code
    4. Uses LLM to reason and generate an answer

    Args:
        request: Contains repo_url and question

    Returns:
        AnalyzeResponse with the answer and session_id for follow-ups
    """
    start_time = datetime.utcnow()

    # Check if we need to index first
    if request.force_reindex or not indexing_service.is_indexed(request.repo_url):
        index_result = await indexing_service.index_repository(
            request.repo_url,
            force=request.force_reindex
        )
        if not index_result.success:
            raise AnalysisError(f"Failed to index repository: {index_result.errors}")

    # Run the analysis
    result = await orchestrator.analyze(
        question=request.question,
        repo_url=request.repo_url
    )

    # Calculate duration
    duration = (datetime.utcnow() - start_time).total_seconds()

    # Create session for follow-ups
    session_id = session_manager.create_session(
        repo_url=request.repo_url,
        context=result.get("metadata", {})
    )

    # Build response
    metadata = AnalysisMetadata(
        question=request.question,
        repo_url=request.repo_url,
        search_results_count=result.get("metadata", {}).get("search_results_count", 0),
        execution_log=result.get("metadata", {}).get("execution_log", []),
        errors=result.get("metadata", {}).get("errors"),
        duration_seconds=duration
    )

    return AnalyzeResponse(
        success=result.get("success", False),
        answer=result.get("answer"),
        session_id=session_id,
        metadata=metadata,
        error=result.get("error")
    )


@router.post(
    "/follow-up",
    response_model=AnalyzeResponse,
    summary="Follow-up Question",
    description="Ask a follow-up question on an existing analysis session"
)
async def follow_up_question(
    request: FollowUpRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    session_manager: SessionManager = Depends(get_session_manager)
) -> AnalyzeResponse:
    """
    Ask a follow-up question using an existing session.

    The session preserves context from the previous analysis,
    allowing for more efficient follow-up questions.
    """
    # Get session
    session = session_manager.get_session(request.session_id)
    if not session:
        raise SessionNotFoundError(request.session_id)

    start_time = datetime.utcnow()

    # Run analysis with existing context
    result = await orchestrator.analyze(
        question=request.question,
        repo_url=session["repo_url"]
    )

    # Update session
    session_manager.update_session(request.session_id, result.get("metadata", {}))

    duration = (datetime.utcnow() - start_time).total_seconds()

    metadata = AnalysisMetadata(
        question=request.question,
        repo_url=session["repo_url"],
        search_results_count=result.get("metadata", {}).get("search_results_count", 0),
        execution_log=result.get("metadata", {}).get("execution_log", []),
        errors=result.get("metadata", {}).get("errors"),
        duration_seconds=duration
    )

    return AnalyzeResponse(
        success=result.get("success", False),
        answer=result.get("answer"),
        session_id=request.session_id,
        metadata=metadata,
        error=result.get("error")
    )


@router.post(
    "/index",
    response_model=IndexResponse,
    summary="Index Repository",
    description="Index a repository for search (without asking a question)"
)
async def index_repository(
    request: IndexRequest,
    indexing_service: IndexingService = Depends(get_indexing_service)
) -> IndexResponse:
    """
    Index a repository without performing analysis.

    Useful for pre-indexing repositories to speed up later queries.
    """
    start_time = datetime.utcnow()

    result = await indexing_service.index_repository(
        request.repo_url,
        force=request.force
    )

    duration = (datetime.utcnow() - start_time).total_seconds()

    return IndexResponse(
        success=result.success,
        repo_url=request.repo_url,
        stats={
            "total_files": result.total_files,
            "indexed_files": result.indexed_files,
            "total_chunks": result.total_chunks,
            "skipped_files": result.skipped_files,
            "errors": result.errors if result.errors else None
        },
        error=result.errors[0] if result.errors and not result.success else None,
        duration_seconds=duration
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search Code",
    description="Search for code in an indexed repository"
)
async def search_code(
    request: SearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
    indexing_service: IndexingService = Depends(get_indexing_service)
) -> SearchResponse:
    """
    Search for code snippets in an indexed repository.

    Uses semantic search to find relevant code based on the query.
    """
    # Check if indexed
    if not indexing_service.is_indexed(request.repo_url):
        return SearchResponse(
            success=False,
            query=request.query,
            results=[],
            total_results=0,
            error="Repository not indexed. Please index first."
        )

    # Generate query embedding
    query_embedding = await embedding_service.embed(request.query)

    # Search vector store
    raw_results = await vector_store.search(
        embedding=query_embedding,
        top_k=request.top_k
    )

    # Filter by file pattern if specified
    if request.file_pattern:
        raw_results = [
            r for r in raw_results
            if request.file_pattern.replace("*", "") in r.get("metadata", {}).get("file_path", "")
        ]

    # Convert to response format
    results = [
        SearchResult(
            file_path=r.get("metadata", {}).get("file_path", ""),
            content=r.get("content", ""),
            score=r.get("score", 0),
            chunk_index=r.get("metadata", {}).get("chunk_index", 0),
            language=r.get("metadata", {}).get("language", ""),
            start_line=r.get("metadata", {}).get("start_line"),
            end_line=r.get("metadata", {}).get("end_line")
        )
        for r in raw_results
    ]

    return SearchResponse(
        success=True,
        query=request.query,
        results=results,
        total_results=len(results)
    )


@router.get(
    "/status/{repo_url:path}",
    response_model=RepoStatusResponse,
    summary="Repository Status",
    description="Get the indexing status of a repository"
)
async def get_repo_status(
    repo_url: str,
    repo_service: RepoService = Depends(get_repo_service),
    indexing_service: IndexingService = Depends(get_indexing_service)
) -> RepoStatusResponse:
    """
    Get the status of a repository.

    Returns whether it's indexed and basic statistics.
    """
    try:
        repo_info = repo_service.parse_github_url(repo_url)
        is_indexed = indexing_service.is_indexed(repo_url)

        stats = None
        if is_indexed:
            # Try to get stats if repo is cloned
            cache_key = f"{repo_info.owner}/{repo_info.name}"
            # Stats would be retrieved from stored metadata in production

        from app.models.schemas import Repository
        repository = Repository(
            url=repo_url,
            owner=repo_info.owner,
            name=repo_info.name,
            branch=repo_info.branch,
            is_indexed=is_indexed
        )

        return RepoStatusResponse(
            success=True,
            repository=repository,
            is_indexed=is_indexed,
            stats=stats
        )

    except ValueError as e:
        return RepoStatusResponse(
            success=False,
            is_indexed=False,
            error=str(e)
        )


@router.delete(
    "/session/{session_id}",
    summary="Delete Session",
    description="Delete an analysis session"
)
async def delete_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
) -> dict:
    """Delete an analysis session."""
    deleted = session_manager.delete_session(session_id)

    if not deleted:
        raise SessionNotFoundError(session_id)

    return {
        "success": True,
        "message": f"Session {session_id} deleted"
    }
