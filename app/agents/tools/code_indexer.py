"""
Code Indexer Tool - Indexes repository code into vector store.

RESPONSIBILITY:
Processes all code files in a repository, generates embeddings,
and stores them in a vector database for semantic search.

FLOW:
1. Scan repository for code files
2. Read and chunk each file
3. Generate embeddings for chunks
4. Store in vector database
5. Return indexing statistics
"""

from pathlib import Path
from typing import List, Dict, Any

from app.agents.base import BaseTool, AgentContext, ToolResult, ToolType


# File extensions to index
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",  # Python & JavaScript
    ".java", ".kt", ".scala",              # JVM languages
    ".go", ".rs", ".c", ".cpp", ".h",      # Systems languages
    ".rb", ".php", ".swift",               # Other languages
    ".sql", ".graphql",                    # Query languages
    ".yaml", ".yml", ".json", ".toml",     # Config files
    ".md", ".rst", ".txt",                 # Documentation
}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
}


class CodeIndexerTool(BaseTool):
    """
    Indexes code files into a vector store for semantic search.

    Features:
    - Smart file filtering (code files only)
    - Chunking for large files
    - Embedding generation
    - Progress tracking
    """

    name = ToolType.CODE_INDEXER.value
    description = "Indexes repository code into searchable vector store"

    def __init__(
        self,
        embedding_service: Any,
        vector_store: Any,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the indexer.

        Args:
            embedding_service: Service to generate embeddings
            vector_store: Vector database for storage
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def execute(self, context: AgentContext, **kwargs) -> ToolResult:
        """
        Index the repository in context.repo_path.

        Args:
            context: Contains repo_path to index

        Returns:
            ToolResult with indexing statistics
        """
        if not context.repo_path:
            return ToolResult(
                success=False,
                error="No repository path available. Run CodeLoader first."
            )

        repo_path = Path(context.repo_path)
        if not repo_path.exists():
            return ToolResult(
                success=False,
                error=f"Repository path does not exist: {repo_path}"
            )

        context.log(f"CodeIndexer: Indexing repository at {repo_path}")

        try:
            # Collect all code files
            files = self._collect_files(repo_path)
            context.log(f"CodeIndexer: Found {len(files)} files to index")

            # Process and index files
            stats = await self._index_files(files, context)

            context.is_indexed = True
            return ToolResult(
                success=True,
                data=stats
            )

        except Exception as e:
            error_msg = f"Indexing failed: {str(e)}"
            context.add_error(error_msg)
            return ToolResult(success=False, error=error_msg)

    def _collect_files(self, repo_path: Path) -> List[Path]:
        """
        Collect all indexable code files from repository.

        Filters by extension and skips common non-code directories.
        """
        files = []

        for file_path in repo_path.rglob("*"):
            # Skip directories
            if file_path.is_dir():
                continue

            # Skip files in ignored directories
            if any(skip_dir in file_path.parts for skip_dir in SKIP_DIRS):
                continue

            # Only include files with code extensions
            if file_path.suffix.lower() in CODE_EXTENSIONS:
                files.append(file_path)

        return files

    async def _index_files(
        self,
        files: List[Path],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Process and index all collected files.

        Returns statistics about the indexing process.
        """
        stats = {
            "total_files": len(files),
            "indexed_files": 0,
            "total_chunks": 0,
            "skipped_files": 0,
            "errors": []
        }

        for file_path in files:
            try:
                # Read file content
                content = self._read_file(file_path)
                if not content:
                    stats["skipped_files"] += 1
                    continue

                # Split into chunks
                chunks = self._chunk_content(content, file_path)

                # Generate embeddings and store
                for chunk in chunks:
                    embedding = await self.embedding_service.embed(chunk["content"])
                    await self.vector_store.add(
                        id=chunk["id"],
                        embedding=embedding,
                        metadata=chunk["metadata"]
                    )

                stats["indexed_files"] += 1
                stats["total_chunks"] += len(chunks)

            except Exception as e:
                stats["errors"].append(f"{file_path}: {str(e)}")

        context.log(
            f"CodeIndexer: Indexed {stats['indexed_files']} files, "
            f"{stats['total_chunks']} chunks"
        )

        return stats

    def _read_file(self, file_path: Path) -> str:
        """Read file content, handling encoding issues."""
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return file_path.read_text(encoding="latin-1")
            except Exception:
                return ""

    def _chunk_content(
        self,
        content: str,
        file_path: Path
    ) -> List[Dict[str, Any]]:
        """
        Split content into overlapping chunks.

        Each chunk includes metadata about its source.
        """
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(content):
            # Calculate end position
            end = start + self.chunk_size

            # Try to break at a newline for cleaner chunks
            if end < len(content):
                newline_pos = content.rfind("\n", start, end)
                if newline_pos > start:
                    end = newline_pos + 1

            chunk_content = content[start:end]

            chunks.append({
                "id": f"{file_path}:{chunk_index}",
                "content": chunk_content,
                "metadata": {
                    "file_path": str(file_path),
                    "chunk_index": chunk_index,
                    "start_char": start,
                    "end_char": end,
                    "language": file_path.suffix.lstrip(".")
                }
            })

            # Move start position with overlap
            start = end - self.chunk_overlap
            chunk_index += 1

        return chunks
