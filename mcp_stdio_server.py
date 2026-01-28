#!/usr/bin/env python3
"""
MCP Code Navigator - Local code exploration tools for LLMs.

Provides fast, incremental code navigation tools over MCP stdio protocol.
Think like a senior engineer: browse structure, search for patterns,
read specific files. No indexing, no embeddings, no waiting.

Tools:
    repo_overview  - High-level repo structure, README, stack detection
    list_directory - Browse directory contents with depth control
    search_code    - Ripgrep-powered regex search across codebase
    read_file      - Read file content with optional line ranges
    find_files     - Find files matching glob patterns

Works with:
    - Local directories (instant)
    - GitHub URLs (shallow clone on first use, cached after)
"""

import asyncio
import logging
import os
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as e:
    print("Error: MCP package not installed. Install with: pip install mcp>=1.0.0", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)

from app.core.config import get_settings
from app.services.repo_service import RepoService, RepoServiceConfig
from app.services import navigator
from app.services.overview import get_overview

# Logging to stderr (stdout is MCP protocol)
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
        _repo_service = RepoService(RepoServiceConfig(
            storage_path=settings.repo_storage_path,
            cache_ttl_hours=settings.repo_cache_ttl_hours,
            clone_timeout_seconds=settings.repo_clone_timeout_seconds,
        ))
    return _repo_service


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS = [
    Tool(
        name="repo_overview",
        description=(
            "Get a high-level overview of a repository: directory tree, "
            "README content, detected tech stack (languages, frameworks, tools), "
            "file statistics, and entry points. Use this FIRST when exploring "
            "an unfamiliar codebase. Accepts local paths or GitHub URLs."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Local directory path or GitHub URL (e.g., /path/to/repo or https://github.com/owner/repo)"
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="list_directory",
        description=(
            "List contents of a directory with depth control. Shows files and "
            "subdirectories as a tree. Use to explore specific parts of a codebase."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list"
                },
                "depth": {
                    "type": "integer",
                    "description": "How many levels deep to show (default: 2)",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="search_code",
        description=(
            "Search for a regex pattern across the codebase using ripgrep. "
            "Returns matching lines with file paths, line numbers, and context. "
            "Fast even on very large repos (100k+ files). "
            "Use to find function definitions, imports, error handling, etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Regex pattern to search for (e.g., 'def authenticate', 'import.*jwt', 'TODO')"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in"
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by language (e.g., 'python', 'js', 'ts', 'go', 'rust', 'java')"
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default: false)",
                    "default": False,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max matches to return (default: 50)",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["query", "path"],
        },
    ),
    Tool(
        name="read_file",
        description=(
            "Read the contents of a file with line numbers. Optionally read "
            "only a specific line range. Use after search_code to examine "
            "specific files, or to read config files, READMEs, etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Start reading from this line (1-indexed, inclusive)",
                    "minimum": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Stop reading at this line (1-indexed, inclusive)",
                    "minimum": 1,
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="find_files",
        description=(
            "Find files matching a glob pattern. Use to locate files by name "
            "or extension. Examples: '**/*.py', 'src/**/*.ts', '**/test_*.py', "
            "'**/config.*', 'docker-compose*.yml'"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')"
                },
                "path": {
                    "type": "string",
                    "description": "Base directory to search from"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max files to return (default: 100)",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 500,
                },
            },
            "required": ["pattern", "path"],
        },
    ),
]


# =============================================================================
# TOOL HANDLERS
# =============================================================================


async def handle_repo_overview(args: dict[str, Any]) -> str:
    """Handle repo_overview tool call."""
    path_or_url = args["path"]

    # Resolve path (handles both local and GitHub URLs)
    repo_service = _get_repo_service()
    try:
        local_path = await repo_service.resolve_path(path_or_url)
    except ValueError as e:
        return f"Error: {e}"
    except (TimeoutError, RuntimeError) as e:
        return f"Error cloning repository: {e}"

    overview = get_overview(local_path)

    if overview.error:
        return f"Error: {overview.error}"

    # Build output
    parts = []
    parts.append(f"# Repository: {overview.name}")
    parts.append(f"Local path: {overview.path}")
    parts.append("")

    # Stack
    if overview.stack.languages or overview.stack.frameworks or overview.stack.tools:
        parts.append("## Tech Stack")
        if overview.stack.languages:
            parts.append(f"Languages: {', '.join(overview.stack.languages)}")
        if overview.stack.frameworks:
            parts.append(f"Frameworks: {', '.join(overview.stack.frameworks)}")
        if overview.stack.tools:
            parts.append(f"Tools: {', '.join(overview.stack.tools)}")
        parts.append("")

    # Stats
    stats = overview.file_stats
    parts.append(f"## Stats: {stats.get('total_files', 0)} files, {stats.get('total_size_mb', 0)} MB")
    if stats.get("top_extensions"):
        ext_str = ", ".join(f"{ext} ({count})" for ext, count in stats["top_extensions"][:10])
        parts.append(f"Extensions: {ext_str}")
    parts.append("")

    # Entry points
    if overview.entry_points:
        parts.append(f"## Entry Points: {', '.join(overview.entry_points)}")
        parts.append("")

    # Config files
    if overview.config_files:
        parts.append(f"## Config Files: {', '.join(overview.config_files)}")
        parts.append("")

    # Tree
    parts.append("## Directory Structure")
    parts.append("```")
    parts.append(overview.tree)
    parts.append("```")
    parts.append("")

    # README
    if overview.readme and overview.readme != "(No README found)":
        parts.append("## README")
        parts.append(overview.readme)

    return "\n".join(parts)


async def handle_list_directory(args: dict[str, Any]) -> str:
    """Handle list_directory tool call."""
    path = args["path"]
    depth = args.get("depth", 2)

    entries, total = navigator.list_directory(path, depth=depth)
    if not entries:
        return f"Directory is empty or not found: {path}"

    tree = navigator.format_tree(entries)
    name = os.path.basename(os.path.abspath(path))
    return f"{name}/\n{tree}\n\n({total} entries shown)"


async def handle_search_code(args: dict[str, Any]) -> str:
    """Handle search_code tool call."""
    result = await navigator.search_code(
        pattern=args["query"],
        path=args["path"],
        file_type=args.get("file_type"),
        max_results=args.get("max_results", 50),
        context_lines=2,
        ignore_case=args.get("ignore_case", False),
    )

    if result.error:
        return f"Error: {result.error}"

    if not result.matches:
        return f"No matches found for pattern: {result.pattern}"

    parts = [f"Found {result.total_matches} matches for `{result.pattern}`"]
    if result.truncated:
        parts[0] += " (truncated)"
    parts.append("")

    current_file = None
    for m in result.matches:
        if m.file != current_file:
            current_file = m.file
            parts.append(f"### {m.file}")

        parts.append(f"  {m.line_number}: {m.content}")
        for ctx in m.context_after:
            parts.append(f"       {ctx}")

    return "\n".join(parts)


async def handle_read_file(args: dict[str, Any]) -> str:
    """Handle read_file tool call."""
    result = navigator.read_file(
        path=args["path"],
        start_line=args.get("start_line"),
        end_line=args.get("end_line"),
    )

    if result.error:
        return f"Error: {result.error}"

    parts = []
    lang_str = f" [{result.language}]" if result.language else ""
    range_str = ""
    if args.get("start_line") or args.get("end_line"):
        range_str = f" (lines {result.start_line}-{result.end_line})"

    parts.append(f"## {os.path.basename(result.path)}{lang_str}{range_str}")
    parts.append(f"Path: {result.path}")
    parts.append(f"Total lines: {result.total_lines} | Size: {result.size_bytes} bytes")
    parts.append("")
    parts.append(result.content)

    return "\n".join(parts)


async def handle_find_files(args: dict[str, Any]) -> str:
    """Handle find_files tool call."""
    results = navigator.find_files(
        pattern=args["pattern"],
        path=args["path"],
        max_results=args.get("max_results", 100),
    )

    if not results:
        return f"No files found matching pattern: {args['pattern']}"

    parts = [f"Found {len(results)} files matching `{args['pattern']}`:", ""]
    for f in results:
        size_str = navigator._format_size(f.size)
        parts.append(f"  {f.path} ({size_str})")

    return "\n".join(parts)


# =============================================================================
# TOOL DISPATCH
# =============================================================================

TOOL_HANDLERS = {
    "repo_overview": handle_repo_overview,
    "list_directory": handle_list_directory,
    "search_code": handle_search_code,
    "read_file": handle_read_file,
    "find_files": handle_find_files,
}


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("scout-code-navigator")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        try:
            result = await handler(arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            logger.exception(f"Error in tool {name}: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


# =============================================================================
# ENTRY POINTS
# =============================================================================


async def main():
    """Main async entry point."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info("Tools: repo_overview, list_directory, search_code, read_file, find_files")

    server = create_mcp_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
