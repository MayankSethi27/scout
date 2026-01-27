"""
API Request Models - Pydantic models for request validation.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class AnalyzeRequest(BaseModel):
    """
    Request to analyze a codebase and answer a question.

    Example:
        {
            "repo_url": "https://github.com/fastapi/fastapi",
            "question": "How does dependency injection work?"
        }
    """
    repo_url: str = Field(
        ...,
        description="GitHub repository URL",
        examples=["https://github.com/owner/repo"]
    )
    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Question about the codebase",
        examples=["How does authentication work?"]
    )
    force_reindex: bool = Field(
        default=False,
        description="Force re-indexing even if already indexed"
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate that URL is a valid GitHub repository URL."""
        patterns = [
            r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+/?$",
            r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+\.git$",
            r"^git@github\.com:[\w\-\.]+/[\w\-\.]+\.git$",
        ]
        v = v.strip()
        if not any(re.match(p, v) for p in patterns):
            raise ValueError("Invalid GitHub repository URL")
        return v


class IndexRequest(BaseModel):
    """
    Request to index a repository.

    Example:
        {
            "repo_url": "https://github.com/owner/repo",
            "force": false
        }
    """
    repo_url: str = Field(
        ...,
        description="GitHub repository URL to index"
    )
    force: bool = Field(
        default=False,
        description="Force re-indexing"
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate GitHub URL."""
        if "github.com" not in v:
            raise ValueError("Must be a GitHub URL")
        return v.strip()


class SearchRequest(BaseModel):
    """
    Request to search indexed code.

    Example:
        {
            "repo_url": "https://github.com/owner/repo",
            "query": "authentication middleware",
            "top_k": 10
        }
    """
    repo_url: str = Field(
        ...,
        description="Repository to search in"
    )
    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Search query"
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of results to return"
    )
    file_pattern: Optional[str] = Field(
        default=None,
        description="Filter by file pattern (e.g., '*.py')"
    )


class FollowUpRequest(BaseModel):
    """
    Request for a follow-up question on an existing analysis.

    Example:
        {
            "session_id": "abc123",
            "question": "Can you show me more details about the login function?"
        }
    """
    session_id: str = Field(
        ...,
        description="Session ID from previous analysis"
    )
    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Follow-up question"
    )
