"""
Embedding Service - Local vector embeddings using Sentence Transformers.

RESPONSIBILITY:
Converts text/code into dense vector representations that capture
semantic meaning, enabling similarity search.

FULLY LOCAL - No API calls, no network required, no API keys.

Uses: sentence-transformers/all-MiniLM-L6-v2
  - 384 dimensions
  - Fast inference
  - Good quality for code search
"""

import hashlib
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding service."""
    model: str = "all-MiniLM-L6-v2"
    dimension: int = 384  # all-MiniLM-L6-v2 produces 384-dim vectors
    batch_size: int = 100
    cache_enabled: bool = True
    device: str = "cpu"  # "cpu", "cuda", or "mps"


class LocalEmbeddingProvider:
    """
    Local embedding provider using Sentence Transformers.

    No API calls - runs entirely on local hardware.
    Model is loaded once and reused for all embeddings.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        """
        Initialize the local embedding provider.

        Args:
            model_name: Sentence Transformer model name
            device: Device to run on ("cpu", "cuda", "mps")
        """
        self.model_name = model_name
        self.device = device
        self._model = None
        logger.info(f"Initialized LocalEmbeddingProvider with model: {model_name}")

    @property
    def model(self):
        """Lazy load the model on first use."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Model loaded successfully on device: {self.device}")
        return self._model

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as list of floats
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of vector embeddings
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class EmbeddingService:
    """
    Main embedding service with caching and batching support.

    Fully local - no API keys or network calls required.

    Usage:
        config = EmbeddingConfig()
        service = EmbeddingService(config)

        # Single embedding
        embedding = await service.embed("def hello(): pass")

        # Batch embeddings
        embeddings = await service.embed_many(["code1", "code2"])
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None, **kwargs):
        """
        Initialize embedding service.

        Args:
            config: Embedding configuration
            **kwargs: Ignored (for backwards compatibility with old api_key parameter)
        """
        # Ignore any api_key parameter for backwards compatibility
        if "api_key" in kwargs:
            logger.debug("api_key parameter ignored - using local embeddings")

        self.config = config or EmbeddingConfig()
        self._provider = LocalEmbeddingProvider(
            model_name=self.config.model,
            device=self.config.device
        )
        self._cache: dict = {} if self.config.cache_enabled else None

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Vector embedding as list of floats
        """
        # Check cache
        if self._cache is not None:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                return self._cache[cache_key]

        # Generate embedding
        embedding = await self._provider.embed_text(text)

        # Store in cache
        if self._cache is not None:
            self._cache[cache_key] = embedding

        return embedding

    async def embed_many(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching.

        Args:
            texts: List of texts to embed

        Returns:
            List of vector embeddings
        """
        results = []
        uncached_texts = []
        uncached_indices = []

        # Check cache for each text
        for i, text in enumerate(texts):
            if self._cache is not None:
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    results.append((i, self._cache[cache_key]))
                    continue

            uncached_texts.append(text)
            uncached_indices.append(i)

        # Batch process uncached texts
        if uncached_texts:
            for batch_start in range(0, len(uncached_texts), self.config.batch_size):
                batch_end = batch_start + self.config.batch_size
                batch = uncached_texts[batch_start:batch_end]
                batch_indices = uncached_indices[batch_start:batch_end]

                embeddings = await self._provider.embed_batch(batch)

                for idx, text, emb in zip(batch_indices, batch, embeddings):
                    results.append((idx, emb))

                    # Cache the result
                    if self._cache is not None:
                        cache_key = self._get_cache_key(text)
                        self._cache[cache_key] = emb

        # Sort by original index and extract embeddings
        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self.config.dimension

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        if self._cache is not None:
            self._cache.clear()
