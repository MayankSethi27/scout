"""
Indexing Service - Orchestrates the code indexing pipeline.

RESPONSIBILITY:
Coordinates the full indexing workflow:
1. Get files from repository
2. Parse and chunk code files
3. Generate embeddings
4. Store in vector database

This service ties together RepoService, EmbeddingService, and VectorStore.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import asyncio


@dataclass
class IndexingConfig:
    """Configuration for indexing service."""
    chunk_size: int = 1500
    chunk_overlap: int = 200
    max_file_size_kb: int = 500
    batch_size: int = 50
    supported_extensions: Set[str] = field(default_factory=lambda: {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".kt", ".go", ".rs", ".c", ".cpp", ".h",
        ".rb", ".php", ".swift", ".scala",
        ".sql", ".graphql",
        ".yaml", ".yml", ".json", ".toml",
        ".md", ".rst", ".txt",
    })


@dataclass
class IndexingResult:
    """Result of indexing operation."""
    success: bool
    repo_url: str
    total_files: int
    indexed_files: int
    total_chunks: int
    skipped_files: int
    errors: List[str]
    duration_seconds: float


@dataclass
class FileChunk:
    """A chunk of code with metadata."""
    id: str
    content: str
    file_path: str
    chunk_index: int
    start_line: int
    end_line: int
    language: str
    repo_url: str


class IndexingService:
    """
    Orchestrates code indexing into vector store.

    This service manages the complete indexing pipeline:
    1. Scan repository for code files
    2. Read and chunk each file intelligently
    3. Generate embeddings via EmbeddingService
    4. Store in VectorStore for search

    Usage:
        service = IndexingService(embedding_service, vector_store, repo_service)
        result = await service.index_repository("https://github.com/owner/repo")
    """

    def __init__(
        self,
        embedding_service: Any,
        vector_store: Any,
        repo_service: Any,
        config: Optional[IndexingConfig] = None
    ):
        """
        Initialize indexing service.

        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector database for storage
            repo_service: Service for repository operations
            config: Indexing configuration
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.repo_service = repo_service
        self.config = config or IndexingConfig()

        # Track indexed repositories
        self._indexed_repos: Dict[str, datetime] = {}

    async def index_repository(
        self,
        repo_url: str,
        force: bool = False
    ) -> IndexingResult:
        """
        Index a GitHub repository.

        Args:
            repo_url: Repository URL to index
            force: Force re-indexing even if already indexed

        Returns:
            IndexingResult with statistics
        """
        start_time = datetime.now()
        errors: List[str] = []

        # Check if already indexed
        if not force and repo_url in self._indexed_repos:
            return IndexingResult(
                success=True,
                repo_url=repo_url,
                total_files=0,
                indexed_files=0,
                total_chunks=0,
                skipped_files=0,
                errors=["Already indexed (use force=True to re-index)"],
                duration_seconds=0
            )

        try:
            # Clone/get repository
            repo_info = await self.repo_service.clone(repo_url)

            if not repo_info.local_path:
                raise RuntimeError("Failed to clone repository")

            # Collect files
            files = self._collect_files(repo_info.local_path)
            total_files = len(files)

            # Process files in batches
            indexed_files = 0
            skipped_files = 0
            total_chunks = 0

            chunks_batch: List[FileChunk] = []

            for file_path in files:
                try:
                    # Read and chunk file
                    file_chunks = self._process_file(
                        file_path,
                        repo_url,
                        repo_info.local_path
                    )

                    if not file_chunks:
                        skipped_files += 1
                        continue

                    chunks_batch.extend(file_chunks)
                    indexed_files += 1
                    total_chunks += len(file_chunks)

                    # Process batch when full
                    if len(chunks_batch) >= self.config.batch_size:
                        await self._index_batch(chunks_batch)
                        chunks_batch = []

                except Exception as e:
                    errors.append(f"{file_path}: {str(e)}")
                    skipped_files += 1

            # Process remaining chunks
            if chunks_batch:
                await self._index_batch(chunks_batch)

            # Mark as indexed
            self._indexed_repos[repo_url] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()

            return IndexingResult(
                success=True,
                repo_url=repo_url,
                total_files=total_files,
                indexed_files=indexed_files,
                total_chunks=total_chunks,
                skipped_files=skipped_files,
                errors=errors,
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return IndexingResult(
                success=False,
                repo_url=repo_url,
                total_files=0,
                indexed_files=0,
                total_chunks=0,
                skipped_files=0,
                errors=[str(e)],
                duration_seconds=duration
            )

    def _collect_files(self, repo_path: str) -> List[Path]:
        """Collect all indexable files from repository."""
        extensions = list(self.config.supported_extensions)
        return self.repo_service.list_files(repo_path, extensions)

    def _process_file(
        self,
        file_path: Path,
        repo_url: str,
        repo_root: str
    ) -> List[FileChunk]:
        """
        Process a single file into chunks.

        Args:
            file_path: Path to file
            repo_url: Repository URL
            repo_root: Root path of repository

        Returns:
            List of FileChunk objects
        """
        # Check file size
        try:
            size_kb = file_path.stat().st_size / 1024
            if size_kb > self.config.max_file_size_kb:
                return []
        except OSError:
            return []

        # Read content
        content = self.repo_service.get_file_content(str(file_path))
        if not content.strip():
            return []

        # Get relative path
        relative_path = str(file_path.relative_to(repo_root))

        # Detect language from extension
        language = file_path.suffix.lstrip(".") or "text"

        # Chunk the content
        return self._chunk_content(
            content=content,
            file_path=relative_path,
            repo_url=repo_url,
            language=language
        )

    def _chunk_content(
        self,
        content: str,
        file_path: str,
        repo_url: str,
        language: str
    ) -> List[FileChunk]:
        """
        Split content into overlapping chunks.

        Uses line-aware chunking to avoid breaking in the middle of code blocks.
        """
        lines = content.split("\n")
        chunks: List[FileChunk] = []

        current_chunk_lines: List[str] = []
        current_chunk_start = 0
        current_size = 0
        chunk_index = 0

        for i, line in enumerate(lines):
            line_size = len(line) + 1  # +1 for newline

            # Check if adding this line exceeds chunk size
            if current_size + line_size > self.config.chunk_size and current_chunk_lines:
                # Create chunk
                chunk_content = "\n".join(current_chunk_lines)
                chunk_id = f"{repo_url}:{file_path}:{chunk_index}"

                chunks.append(FileChunk(
                    id=chunk_id,
                    content=chunk_content,
                    file_path=file_path,
                    chunk_index=chunk_index,
                    start_line=current_chunk_start + 1,
                    end_line=i,
                    language=language,
                    repo_url=repo_url
                ))

                # Calculate overlap
                overlap_lines = self._get_overlap_lines(
                    current_chunk_lines,
                    self.config.chunk_overlap
                )

                # Start new chunk with overlap
                current_chunk_lines = overlap_lines
                current_chunk_start = i - len(overlap_lines)
                current_size = sum(len(l) + 1 for l in overlap_lines)
                chunk_index += 1

            current_chunk_lines.append(line)
            current_size += line_size

        # Don't forget the last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            chunk_id = f"{repo_url}:{file_path}:{chunk_index}"

            chunks.append(FileChunk(
                id=chunk_id,
                content=chunk_content,
                file_path=file_path,
                chunk_index=chunk_index,
                start_line=current_chunk_start + 1,
                end_line=len(lines),
                language=language,
                repo_url=repo_url
            ))

        return chunks

    def _get_overlap_lines(
        self,
        lines: List[str],
        target_overlap: int
    ) -> List[str]:
        """Get lines for overlap from end of chunk."""
        overlap_lines: List[str] = []
        overlap_size = 0

        for line in reversed(lines):
            line_size = len(line) + 1
            if overlap_size + line_size > target_overlap:
                break
            overlap_lines.insert(0, line)
            overlap_size += line_size

        return overlap_lines

    async def _index_batch(self, chunks: List[FileChunk]) -> None:
        """
        Index a batch of chunks.

        Generates embeddings and stores in vector database.
        """
        if not chunks:
            return

        # Extract content for embedding
        contents = [chunk.content for chunk in chunks]

        # Generate embeddings
        embeddings = await self.embedding_service.embed_many(contents)

        # Prepare items for vector store
        items = []
        for chunk, embedding in zip(chunks, embeddings):
            items.append({
                "id": chunk.id,
                "embedding": embedding,
                "content": chunk.content,
                "metadata": {
                    "file_path": chunk.file_path,
                    "chunk_index": chunk.chunk_index,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": chunk.language,
                    "repo_url": chunk.repo_url
                }
            })

        # Store in vector database
        await self.vector_store.add_batch(items)

    def is_indexed(self, repo_url: str) -> bool:
        """Check if repository has been indexed."""
        return repo_url in self._indexed_repos

    async def clear_index(self, repo_url: str) -> bool:
        """
        Clear index for a specific repository.

        Args:
            repo_url: Repository URL

        Returns:
            True if cleared successfully
        """
        if repo_url in self._indexed_repos:
            del self._indexed_repos[repo_url]
            await self.vector_store.delete_by_repo(repo_url)
            return True
        return False

    async def clear_all(self) -> None:
        """Clear all indexed data."""
        self._indexed_repos.clear()
        await self.vector_store.clear()
