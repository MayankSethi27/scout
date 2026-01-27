"""
Vector Store - Stores and searches vector embeddings.

RESPONSIBILITY:
Provides persistent storage for code embeddings and efficient
similarity search for finding relevant code snippets.

SUPPORTED BACKENDS:
- ChromaDB (local, recommended for development)
- Pinecone (cloud, recommended for production)
- In-Memory (testing only)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid


@dataclass
class VectorStoreConfig:
    """Configuration for vector store."""
    backend: str = "chroma"  # chroma, pinecone, memory
    collection_name: str = "codebase"
    persist_directory: str = "./vector_db"
    # Pinecone specific
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None


@dataclass
class SearchResult:
    """Result from vector similarity search."""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseVectorBackend(ABC):
    """Base class for vector store backends."""

    @abstractmethod
    async def add(
        self,
        id: str,
        embedding: List[float],
        content: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Add a single embedding."""
        pass

    @abstractmethod
    async def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        contents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> None:
        """Add multiple embeddings."""
        pass

    @abstractmethod
    async def search(
        self,
        embedding: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for similar embeddings."""
        pass

    @abstractmethod
    async def delete(self, ids: List[str]) -> None:
        """Delete embeddings by ID."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all embeddings."""
        pass


class InMemoryBackend(BaseVectorBackend):
    """
    In-memory vector store for testing.

    Not recommended for production - no persistence.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    async def add(
        self,
        id: str,
        embedding: List[float],
        content: str,
        metadata: Dict[str, Any]
    ) -> None:
        self._store[id] = {
            "embedding": embedding,
            "content": content,
            "metadata": metadata
        }

    async def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        contents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> None:
        for id, emb, content, meta in zip(ids, embeddings, contents, metadatas):
            await self.add(id, emb, content, meta)

    async def search(
        self,
        embedding: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search using cosine similarity."""
        results = []

        for id, data in self._store.items():
            # Apply filter if provided
            if filter and not self._matches_filter(data["metadata"], filter):
                continue

            score = self._cosine_similarity(embedding, data["embedding"])
            results.append(SearchResult(
                id=id,
                content=data["content"],
                score=score,
                metadata=data["metadata"]
            ))

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def delete(self, ids: List[str]) -> None:
        for id in ids:
            self._store.pop(id, None)

    async def clear(self) -> None:
        self._store.clear()

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def _matches_filter(self, metadata: Dict, filter: Dict) -> bool:
        """Check if metadata matches filter criteria."""
        for key, condition in filter.items():
            if key not in metadata:
                return False
            if isinstance(condition, dict):
                if "$contains" in condition:
                    if condition["$contains"] not in str(metadata[key]):
                        return False
            elif metadata[key] != condition:
                return False
        return True


class ChromaBackend(BaseVectorBackend):
    """
    ChromaDB backend for local persistent storage.

    Recommended for development and small-scale production.
    """

    def __init__(self, collection_name: str, persist_directory: str):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self._client = None
        self._collection = None

    @property
    def collection(self):
        """Lazy initialization of ChromaDB collection."""
        if self._collection is None:
            import chromadb

            # ChromaDB 1.x uses PersistentClient for local storage
            self._client = chromadb.PersistentClient(
                path=self.persist_directory
            )

            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        return self._collection

    async def add(
        self,
        id: str,
        embedding: List[float],
        content: str,
        metadata: Dict[str, Any]
    ) -> None:
        self.collection.add(
            ids=[id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )

    async def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        contents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> None:
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )

    async def search(
        self,
        embedding: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=filter
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, id in enumerate(results["ids"][0]):
                search_results.append(SearchResult(
                    id=id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    score=1 - results["distances"][0][i] if results["distances"] else 0,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {}
                ))

        return search_results

    async def delete(self, ids: List[str]) -> None:
        self.collection.delete(ids=ids)

    async def clear(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = None


class VectorStore:
    """
    Main vector store service with pluggable backends.

    Usage:
        store = VectorStore(config)
        await store.add("id1", embedding, "code content", {"file": "main.py"})
        results = await store.search(query_embedding, top_k=5)
    """

    def __init__(self, config: Optional[VectorStoreConfig] = None):
        """
        Initialize vector store.

        Args:
            config: Vector store configuration
        """
        self.config = config or VectorStoreConfig()
        self._backend = self._create_backend()

    def _create_backend(self) -> BaseVectorBackend:
        """Create the appropriate backend."""
        if self.config.backend == "memory":
            return InMemoryBackend()

        elif self.config.backend == "chroma":
            return ChromaBackend(
                collection_name=self.config.collection_name,
                persist_directory=self.config.persist_directory
            )

        elif self.config.backend == "pinecone":
            raise NotImplementedError("Pinecone backend not yet implemented")

        else:
            raise ValueError(f"Unknown backend: {self.config.backend}")

    async def add(
        self,
        id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: str = ""
    ) -> None:
        """
        Add an embedding to the store.

        Args:
            id: Unique identifier
            embedding: Vector embedding
            metadata: Additional metadata
            content: Original text content
        """
        await self._backend.add(
            id=id,
            embedding=embedding,
            content=content,
            metadata=metadata or {}
        )

    async def add_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> None:
        """
        Add multiple embeddings.

        Args:
            items: List of dicts with id, embedding, content, metadata
        """
        ids = [item["id"] for item in items]
        embeddings = [item["embedding"] for item in items]
        contents = [item.get("content", "") for item in items]
        metadatas = [item.get("metadata", {}) for item in items]

        await self._backend.add_batch(ids, embeddings, contents, metadatas)

    async def search(
        self,
        embedding: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings.

        Args:
            embedding: Query embedding
            top_k: Number of results
            filter: Metadata filter

        Returns:
            List of search results with score, content, metadata
        """
        results = await self._backend.search(embedding, top_k, filter)

        return [
            {
                "id": r.id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata
            }
            for r in results
        ]

    async def delete(self, ids: List[str]) -> None:
        """Delete embeddings by ID."""
        await self._backend.delete(ids)

    async def delete_by_repo(self, repo_url: str) -> None:
        """Delete all embeddings for a repository."""
        # This would require backend-specific implementation
        # For now, we track by metadata filter
        pass

    async def clear(self) -> None:
        """Clear all embeddings."""
        await self._backend.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        if isinstance(self._backend, InMemoryBackend):
            return {"count": len(self._backend._store)}
        return {"count": "unknown"}
