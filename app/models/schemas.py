"""
Core Domain Schemas - Shared data models used across the application.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AnalysisStatus(str, Enum):
    """Status of an analysis operation."""
    PENDING = "pending"
    CLONING = "cloning"
    INDEXING = "indexing"
    SEARCHING = "searching"
    REASONING = "reasoning"
    COMPLETED = "completed"
    FAILED = "failed"


class Repository(BaseModel):
    """Repository information."""
    url: str
    owner: str
    name: str
    branch: Optional[str] = None
    local_path: Optional[str] = None
    is_indexed: bool = False
    indexed_at: Optional[datetime] = None


class CodeChunk(BaseModel):
    """A chunk of code from the repository."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    score: Optional[float] = None


class SearchResult(BaseModel):
    """Result from semantic search."""
    file_path: str
    content: str
    score: float
    chunk_index: int
    language: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class ExecutionStep(BaseModel):
    """A step in the execution plan."""
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None


class ExecutionPlan(BaseModel):
    """Plan created by the planner agent."""
    analysis: str
    steps: List[ExecutionStep]


class AnalysisMetadata(BaseModel):
    """Metadata about an analysis operation."""
    question: str
    repo_url: str
    search_results_count: int
    execution_log: List[str] = Field(default_factory=list)
    errors: Optional[List[str]] = None
    duration_seconds: Optional[float] = None
