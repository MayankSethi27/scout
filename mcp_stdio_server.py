#!/usr/bin/env python3
"""
MCP Server (stdio) - GitHub Code Retrieval for Claude Desktop.

This MCP server provides Claude with direct access to GitHub codebases
using the standard MCP stdio protocol for Claude Desktop integration.

FULLY LOCAL:
- No API keys required
- No network calls for embeddings
- Uses sentence-transformers/all-MiniLM-L6-v2 for local embeddings

Install:
    pip install github-code-retrieval

Add to Claude Desktop config (~/.config/claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "github-code-retrieval": {
          "command": "github-code-retrieval"
        }
      }
    }

Tool: analyze_github_repo
  - Clones and indexes GitHub repositories
  - Performs semantic search for relevant code
  - Returns structured code snippets with full context
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as e:
    print(f"Error: MCP package not installed. Install with: pip install mcp>=1.0.0", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService, EmbeddingConfig
from app.services.vector_store import VectorStore, VectorStoreConfig
from app.services.repo_service import RepoService, RepoServiceConfig
from app.services.indexing_service import IndexingService, IndexingConfig

# Configure logging to stderr (stdout is for MCP protocol)
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
# INPUT/OUTPUT SCHEMAS
# =============================================================================


class AnalyzeRepoInput(BaseModel):
    repo_url: str = Field(
        ...,
        description="GitHub repository URL (e.g., https://github.com/owner/repo)",
        min_length=10,
    )
    question: str = Field(
        ...,
        description="Question or search query to find relevant code",
        min_length=3,
        max_length=1000,
    )
    top_k: int = Field(
        default=10,
        description="Number of code snippets to retrieve (1-30)",
        ge=1,
        le=30,
    )


class CodeSnippet(BaseModel):
    file_path: str = Field(..., description="Path to the file in the repository")
    content: str = Field(..., description="The code content")
    start_line: int | None = Field(None, description="Starting line number (1-indexed)")
    end_line: int | None = Field(None, description="Ending line number (1-indexed)")
    language: str = Field("", description="Programming language")
    relevance_score: float = Field(..., description="Semantic similarity score (0-1)")
    chunk_index: int = Field(0, description="Index of this chunk within the file")


class RepositoryInfo(BaseModel):
    url: str
    owner: str
    name: str
    local_path: str | None = None
    total_files_indexed: int = 0
    total_chunks: int = 0


class AnalyzeRepoOutput(BaseModel):
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


# =============================================================================
# MCP SERVER IMPLEMENTATION
# =============================================================================


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("github-code-retrieval")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="analyze_github_repo",
                description="""Retrieve relevant code from a GitHub repository to answer questions.

This tool performs semantic code search and returns structured code context:
1. Clones the repository (cached for performance)
2. Indexes all code files using local embeddings (no API keys needed)
3. Searches for code snippets relevant to your question
4. Returns ranked code snippets with file paths and line numbers

USE THIS TOOL when you need to:
- Understand how a codebase works
- Find specific implementations
- Answer questions about code structure
- Locate where functionality is defined

Returns: List of relevant code snippets with file paths, line numbers, and relevance scores.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_url": {
                            "type": "string",
                            "description": "GitHub repository URL (e.g., https://github.com/owner/repo)"
                        },
                        "question": {
                            "type": "string",
                            "description": "Question or search query to find relevant code"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of code snippets to retrieve (default: 10, max: 30)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 30
                        }
                    },
                    "required": ["repo_url", "question"]
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name != "analyze_github_repo":
            raise ValueError(f"Unknown tool: {name}")
        return await handle_analyze_repo(arguments)

    return server


async def handle_analyze_repo(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle the analyze_github_repo tool call."""
    start_time = datetime.utcnow()

    try:
        # Validate input
        try:
            input_data = AnalyzeRepoInput(**arguments)
        except ValidationError as e:
            output = AnalyzeRepoOutput(
                success=False,
                repository=RepositoryInfo(url="", owner="", name=""),
                query=arguments.get("question", ""),
                error=f"Invalid input: {e.errors()}"
            )
            return [TextContent(type="text", text=output.model_dump_json(indent=2))]

        logger.info(f"Retrieving code from: {input_data.repo_url}")
        logger.info(f"Query: {input_data.question[:100]}...")

        # Get services
        repo_service = get_repo_service()
        indexing_service = get_indexing_service()
        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        # Parse repository URL
        try:
            repo_info = repo_service.parse_github_url(input_data.repo_url)
        except ValueError as e:
            output = AnalyzeRepoOutput(
                success=False,
                repository=RepositoryInfo(url=input_data.repo_url, owner="", name=""),
                query=input_data.question,
                error=f"Invalid repository URL: {e}"
            )
            return [TextContent(type="text", text=output.model_dump_json(indent=2))]

        # Index repository if needed
        index_stats = {"total_files": 0, "total_chunks": 0}
        if not indexing_service.is_indexed(input_data.repo_url):
            logger.info("Repository not indexed, starting indexing...")
            index_result = await indexing_service.index_repository(input_data.repo_url)

            if not index_result.success:
                output = AnalyzeRepoOutput(
                    success=False,
                    repository=RepositoryInfo(
                        url=input_data.repo_url,
                        owner=repo_info.owner,
                        name=repo_info.name
                    ),
                    query=input_data.question,
                    error=f"Indexing failed: {'; '.join(index_result.errors)}"
                )
                return [TextContent(type="text", text=output.model_dump_json(indent=2))]

            index_stats = {
                "total_files": index_result.indexed_files,
                "total_chunks": index_result.total_chunks
            }
            logger.info(f"Indexed {index_result.indexed_files} files, {index_result.total_chunks} chunks")

        # Perform semantic search
        logger.info(f"Searching for relevant code (top_k={input_data.top_k})...")
        query_embedding = await embedding_service.embed(input_data.question)

        raw_results = await vector_store.search(
            embedding=query_embedding,
            top_k=input_data.top_k
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

        # Build output
        settings = get_settings()
        output = AnalyzeRepoOutput(
            success=True,
            repository=RepositoryInfo(
                url=input_data.repo_url,
                owner=repo_info.owner,
                name=repo_info.name,
                total_files_indexed=index_stats.get("total_files", 0),
                total_chunks=index_stats.get("total_chunks", 0)
            ),
            query=input_data.question,
            code_snippets=code_snippets,
            total_results=len(code_snippets),
            retrieval_metadata={
                "duration_seconds": round(duration, 2),
                "top_k_requested": input_data.top_k,
                "embedding_model": settings.embedding_model,
                "fully_local": True,
            }
        )

        logger.info(f"Retrieved {len(code_snippets)} snippets in {duration:.2f}s")

        return [TextContent(type="text", text=output.model_dump_json(indent=2))]

    except Exception as e:
        logger.exception(f"Error during retrieval: {e}")
        output = AnalyzeRepoOutput(
            success=False,
            repository=RepositoryInfo(url=arguments.get("repo_url", ""), owner="", name=""),
            query=arguments.get("question", ""),
            error=str(e),
            retrieval_metadata={"exception_type": type(e).__name__}
        )
        return [TextContent(type="text", text=output.model_dump_json(indent=2))]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


async def main():
    """Main async entry point for the MCP server."""
    settings = get_settings()

    logger.info(f"Starting {settings.app_name} MCP Server v{settings.app_version}")
    logger.info(f"Embedding model: {settings.embedding_model} (local)")
    logger.info("Mode: Fully local - no API keys required")

    server = create_mcp_server()

    logger.info("MCP Server ready, waiting for connections...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def run():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
