#!/usr/bin/env python3
"""
HTTP Server - Code Navigator API.

FastAPI server exposing the same navigation tools as the MCP stdio server,
accessible over HTTP for non-MCP clients.

Endpoints:
    POST /repo_overview   - Repository overview
    POST /list_directory   - Browse directory
    POST /search_code      - Regex code search
    POST /read_file        - Read file contents
    POST /find_files       - Glob file search
    GET  /health           - Health check
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services import navigator
from app.services.overview import get_overview
from app.services.repo_service import RepoService, RepoServiceConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("scout")

# Lazy-initialized repo service
_repo_service: RepoService | None = None


def _get_repo_service() -> RepoService:
    global _repo_service
    if _repo_service is None:
        settings = get_settings()
        _repo_service = RepoService(
            RepoServiceConfig(
                storage_path=settings.repo_storage_path,
                cache_ttl_hours=settings.repo_cache_ttl_hours,
                clone_timeout_seconds=settings.repo_clone_timeout_seconds,
            )
        )
    return _repo_service


# =============================================================================
# REQUEST / RESPONSE SCHEMAS
# =============================================================================


class RepoOverviewRequest(BaseModel):
    path: str = Field(..., description="Local path or GitHub URL")


class ListDirectoryRequest(BaseModel):
    path: str = Field(..., description="Directory path")
    depth: int = Field(2, ge=1, le=10, description="Depth levels")


class SearchCodeRequest(BaseModel):
    query: str = Field(..., description="Regex pattern")
    path: str = Field(..., description="Directory to search")
    file_type: Optional[str] = Field(None, description="Language filter")
    ignore_case: bool = Field(False, description="Case-insensitive")
    max_results: int = Field(50, ge=1, le=200, description="Max matches")


class ReadFileRequest(BaseModel):
    path: str = Field(..., description="File path")
    start_line: Optional[int] = Field(None, ge=1, description="Start line")
    end_line: Optional[int] = Field(None, ge=1, description="End line")


class FindFilesRequest(BaseModel):
    pattern: str = Field(..., description="Glob pattern")
    path: str = Field(..., description="Base directory")
    max_results: int = Field(100, ge=1, le=500, description="Max results")


class ToolResponse(BaseModel):
    success: bool
    result: str
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = ""
    tools: list[str] = []


# =============================================================================
# FASTAPI APP
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} HTTP Server v{settings.app_version}")
    yield
    logger.info("Shutting down...")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Code Navigator - fast, incremental code exploration API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ENDPOINTS
# =============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        tools=[
            "repo_overview",
            "list_directory",
            "search_code",
            "read_file",
            "find_files",
        ],
    )


@app.post("/repo_overview", response_model=ToolResponse)
async def repo_overview(req: RepoOverviewRequest):
    try:
        repo_service = _get_repo_service()
        local_path = await repo_service.resolve_path(req.path)
        overview = get_overview(local_path)

        if overview.error:
            return ToolResponse(success=False, result="", error=overview.error)

        parts = [
            f"Repository: {overview.name}",
            f"Path: {overview.path}",
        ]
        if overview.stack.languages:
            parts.append(f"Languages: {', '.join(overview.stack.languages)}")
        if overview.stack.frameworks:
            parts.append(f"Frameworks: {', '.join(overview.stack.frameworks)}")

        stats = overview.file_stats
        parts.append(
            f"Files: {stats.get('total_files', 0)}, Size: {stats.get('total_size_mb', 0)} MB"
        )
        parts.append("")
        parts.append(overview.tree)

        if overview.readme and overview.readme != "(No README found)":
            parts.append("")
            parts.append(overview.readme)

        return ToolResponse(success=True, result="\n".join(parts))
    except Exception as e:
        return ToolResponse(success=False, result="", error=str(e))


@app.post("/list_directory", response_model=ToolResponse)
async def list_dir(req: ListDirectoryRequest):
    try:
        entries, total = navigator.list_directory(req.path, depth=req.depth)
        if not entries:
            return ToolResponse(success=True, result=f"Empty or not found: {req.path}")

        tree = navigator.format_tree(entries)
        name = os.path.basename(os.path.abspath(req.path))
        return ToolResponse(
            success=True, result=f"{name}/\n{tree}\n\n({total} entries)"
        )
    except Exception as e:
        return ToolResponse(success=False, result="", error=str(e))


@app.post("/search_code", response_model=ToolResponse)
async def search_code(req: SearchCodeRequest):
    try:
        result = await navigator.search_code(
            pattern=req.query,
            path=req.path,
            file_type=req.file_type,
            max_results=req.max_results,
            context_lines=2,
            ignore_case=req.ignore_case,
        )

        if result.error:
            return ToolResponse(success=False, result="", error=result.error)

        if not result.matches:
            return ToolResponse(success=True, result=f"No matches for: {req.query}")

        lines = [f"Found {result.total_matches} matches for `{req.query}`", ""]
        current_file = None
        for m in result.matches:
            if m.file != current_file:
                current_file = m.file
                lines.append(f"--- {m.file}")
            lines.append(f"  {m.line_number}: {m.content}")

        return ToolResponse(success=True, result="\n".join(lines))
    except Exception as e:
        return ToolResponse(success=False, result="", error=str(e))


@app.post("/read_file", response_model=ToolResponse)
async def read_file(req: ReadFileRequest):
    try:
        result = navigator.read_file(
            path=req.path,
            start_line=req.start_line,
            end_line=req.end_line,
        )
        if result.error:
            return ToolResponse(success=False, result="", error=result.error)

        return ToolResponse(success=True, result=result.content)
    except Exception as e:
        return ToolResponse(success=False, result="", error=str(e))


@app.post("/find_files", response_model=ToolResponse)
async def find_files(req: FindFilesRequest):
    try:
        results = navigator.find_files(
            pattern=req.pattern,
            path=req.path,
            max_results=req.max_results,
        )

        if not results:
            return ToolResponse(
                success=True, result=f"No files matching: {req.pattern}"
            )

        lines = [f"Found {len(results)} files:", ""]
        for f in results:
            size_str = navigator._format_size(f.size)
            lines.append(f"  {f.path} ({size_str})")

        return ToolResponse(success=True, result="\n".join(lines))
    except Exception as e:
        return ToolResponse(success=False, result="", error=str(e))


# =============================================================================
# MAIN
# =============================================================================


def main():
    settings = get_settings()
    uvicorn.run(
        "mcp_server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()
