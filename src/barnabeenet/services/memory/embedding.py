"""Text embedding service using sentence-transformers.

Provides 384-dimensional embeddings for semantic memory search.
Uses all-MiniLM-L6-v2 for fast, accurate embeddings.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Model constants
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingService:
    """Service for generating text embeddings.

    Uses sentence-transformers all-MiniLM-L6-v2 model for:
    - Fast inference (~5ms per text on CPU)
    - Good semantic similarity performance
    - Small model size (~80MB)
    - 384-dimensional output vectors
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Initialize the embedding service.

        Args:
            model_name: Hugging Face model name for embeddings.
        """
        self._model_name = model_name
        self._model = None
        self._initialized = False

    async def init(self) -> None:
        """Initialize the embedding model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            self._initialized = True
            logger.info(
                f"Embedding model loaded: {self._model_name} "
                f"(dim={self._model.get_sentence_embedding_dimension()})"
            )
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._model = None
        self._initialized = False
        logger.info("EmbeddingService shutdown")

    def is_available(self) -> bool:
        """Check if embedding model is available."""
        return self._initialized and self._model is not None

    async def embed(self, text: str) -> NDArray[np.float32]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            384-dimensional embedding vector as numpy array.
        """
        if not self._initialized:
            await self.init()

        if self._model is None:
            raise RuntimeError("Embedding model not available")

        # sentence-transformers encode is sync but fast
        embedding = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Normalize for cosine similarity
        )
        return embedding.astype(np.float32)

    async def embed_batch(self, texts: list[str]) -> NDArray[np.float32]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            Array of shape (n_texts, 384) with embedding vectors.
        """
        if not self._initialized:
            await self.init()

        if self._model is None:
            raise RuntimeError("Embedding model not available")

        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32)

    @staticmethod
    def cosine_similarity(
        query: NDArray[np.float32],
        vectors: NDArray[np.float32],
    ) -> NDArray[np.float32]:
        """Compute cosine similarity between query and vectors.

        Since vectors are normalized, this is just dot product.

        Args:
            query: Single query vector (384,)
            vectors: Array of vectors (n, 384)

        Returns:
            Array of similarity scores (n,)
        """
        if len(vectors) == 0:
            return np.array([], dtype=np.float32)

        # Vectors are normalized, so dot product = cosine similarity
        return np.dot(vectors, query)

    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension."""
        return EMBEDDING_DIM


# Global singleton
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
