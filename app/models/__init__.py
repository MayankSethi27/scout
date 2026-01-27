"""
Data Models for GitHub Codebase Analyst
=======================================

Organized into three categories:
- schemas: Core domain models used across the application
- requests: API request validation models
- responses: API response models
"""

from app.models.schemas import (
    AnalysisStatus,
    Repository,
    CodeChunk,
    SearchResult,
    ExecutionStep,
    ExecutionPlan,
    AnalysisMetadata,
)

from app.models.requests import (
    AnalyzeRequest,
    IndexRequest,
    SearchRequest,
    FollowUpRequest,
)

from app.models.responses import (
    BaseResponse,
    HealthResponse,
    AnalyzeResponse,
    IndexResponse,
    SearchResponse,
    RepoStatusResponse,
    ErrorResponse,
    SessionResponse,
)

__all__ = [
    # Schemas
    "AnalysisStatus",
    "Repository",
    "CodeChunk",
    "SearchResult",
    "ExecutionStep",
    "ExecutionPlan",
    "AnalysisMetadata",
    # Requests
    "AnalyzeRequest",
    "IndexRequest",
    "SearchRequest",
    "FollowUpRequest",
    # Responses
    "BaseResponse",
    "HealthResponse",
    "AnalyzeResponse",
    "IndexResponse",
    "SearchResponse",
    "RepoStatusResponse",
    "ErrorResponse",
    "SessionResponse",
]
