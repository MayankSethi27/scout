"""
API Response Models - Pydantic models for API responses.
"""

from typing import Optional, List, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.schemas import (
    SearchResult,
    AnalysisMetadata,
    AnalysisStatus,
    Repository
)


T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Base response wrapper with standard fields."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AnalyzeResponse(BaseModel):
    """
    Response from code analysis.

    Example:
        {
            "success": true,
            "answer": "Authentication in this codebase works by...",
            "session_id": "abc123",
            "metadata": {...}
        }
    """
    success: bool
    answer: Optional[str] = None
    session_id: str = Field(
        ...,
        description="Session ID for follow-up questions"
    )
    metadata: AnalysisMetadata
    error: Optional[str] = None


class IndexResponse(BaseModel):
    """
    Response from indexing operation.

    Example:
        {
            "success": true,
            "repo_url": "https://github.com/owner/repo",
            "stats": {
                "total_files": 150,
                "indexed_files": 142,
                "total_chunks": 890
            }
        }
    """
    success: bool
    repo_url: str
    stats: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


class SearchResponse(BaseModel):
    """
    Response from search operation.

    Example:
        {
            "success": true,
            "query": "authentication",
            "results": [...],
            "total_results": 10
        }
    """
    success: bool
    query: str
    results: List[SearchResult] = Field(default_factory=list)
    total_results: int = 0
    error: Optional[str] = None


class RepoStatusResponse(BaseModel):
    """
    Response with repository status.

    Example:
        {
            "success": true,
            "repository": {...},
            "is_indexed": true,
            "stats": {...}
        }
    """
    success: bool
    repository: Optional[Repository] = None
    is_indexed: bool = False
    stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """
    Standard error response.

    Example:
        {
            "success": false,
            "error": "Repository not found",
            "error_code": "REPO_NOT_FOUND",
            "details": {...}
        }
    """
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionResponse(BaseModel):
    """
    Response with session information.

    Used for managing analysis sessions.
    """
    session_id: str
    repo_url: str
    created_at: datetime
    last_activity: datetime
    question_count: int = 0
    is_active: bool = True
