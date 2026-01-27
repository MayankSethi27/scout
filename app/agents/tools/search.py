"""
Search Tool - Semantic search over indexed code.

RESPONSIBILITY:
Searches the vector store for code snippets that are semantically
similar to the user's query. Returns ranked results with context.

FLOW:
1. Receive search query (usually the user's question)
2. Generate embedding for the query
3. Search vector store for similar chunks
4. Return ranked results with metadata
"""

from typing import List, Dict, Any, Optional

from app.agents.base import BaseTool, AgentContext, ToolResult, ToolType


class SearchTool(BaseTool):
    """
    Performs semantic search over indexed code.

    Features:
    - Semantic similarity search using embeddings
    - Configurable result count and threshold
    - Returns code snippets with file context
    """

    name = ToolType.SEARCH.value
    description = "Searches for relevant code using semantic similarity"

    def __init__(
        self,
        embedding_service: Any,
        vector_store: Any,
        default_top_k: int = 10,
        score_threshold: float = 0.5
    ):
        """
        Initialize the search tool.

        Args:
            embedding_service: Service to generate query embeddings
            vector_store: Vector database to search
            default_top_k: Default number of results to return
            score_threshold: Minimum similarity score (0-1)
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold

    async def execute(self, context: AgentContext, **kwargs) -> ToolResult:
        """
        Search for code relevant to the query.

        Args:
            context: Contains the search context
            **kwargs:
                query: Search query (defaults to context.question)
                top_k: Number of results (defaults to default_top_k)

        Returns:
            ToolResult with ranked search results
        """
        query = kwargs.get("query") or context.question
        top_k = kwargs.get("top_k", self.default_top_k)

        if not context.is_indexed:
            return ToolResult(
                success=False,
                error="Repository not indexed. Run CodeIndexer first."
            )

        context.log(f"Search: Searching for '{query[:50]}...'")

        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.embed(query)

            # Search vector store
            raw_results = await self.vector_store.search(
                embedding=query_embedding,
                top_k=top_k
            )

            # Filter and format results
            results = self._process_results(raw_results)

            # Store in context for downstream agents
            context.search_results = results

            context.log(f"Search: Found {len(results)} relevant results")

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "result_count": len(results),
                    "results": results
                }
            )

        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            context.add_error(error_msg)
            return ToolResult(success=False, error=error_msg)

    def _process_results(
        self,
        raw_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process and filter raw search results.

        - Filters by score threshold
        - Sorts by relevance
        - Formats for downstream processing
        """
        processed = []

        for result in raw_results:
            score = result.get("score", 0)

            # Filter by threshold
            if score < self.score_threshold:
                continue

            processed.append({
                "file_path": result.get("metadata", {}).get("file_path", "Unknown"),
                "content": result.get("content", ""),
                "score": score,
                "chunk_index": result.get("metadata", {}).get("chunk_index", 0),
                "language": result.get("metadata", {}).get("language", ""),
            })

        # Sort by score descending
        processed.sort(key=lambda x: x["score"], reverse=True)

        return processed

    async def search_by_file_pattern(
        self,
        context: AgentContext,
        pattern: str,
        query: Optional[str] = None
    ) -> ToolResult:
        """
        Search within files matching a pattern.

        Useful for targeted searches like "search in test files".

        Args:
            context: Agent context
            pattern: File pattern (e.g., "test_*.py", "*.ts")
            query: Search query (defaults to context.question)
        """
        query = query or context.question

        try:
            query_embedding = await self.embedding_service.embed(query)

            raw_results = await self.vector_store.search(
                embedding=query_embedding,
                top_k=self.default_top_k * 2,  # Get more, then filter
                filter={"file_path": {"$contains": pattern}}
            )

            results = self._process_results(raw_results)
            context.search_results.extend(results)

            return ToolResult(
                success=True,
                data={"results": results}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Pattern search failed: {str(e)}"
            )
